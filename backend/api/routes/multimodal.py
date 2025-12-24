"""Multimodal extraction and QA endpoints (Phase 6)."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_services_ready
from core.database import get_db
from core.logging import set_document_id, set_phase
from core.metrics import metrics, MetricNames
from core.storage import get_file_path, generate_stored_filename
from models.document import Document
from models.document_table import DocumentTable
from models.document_figure import DocumentFigure
from schemas.multimodal import (
    ExtractVisualsRequest,
    ExtractVisualsResponse,
    TableData,
    FigureData,
)
from services.table_extractor import extract_tables_from_page, process_extracted_table
from services.figure_analyzer import analyze_figures_on_page

logger = logging.getLogger(__name__)

router = APIRouter(tags=["multimodal"])

BATCH_COMMIT_SIZE = 10


async def _get_visual_counts(db: AsyncSession, document_id: uuid.UUID) -> tuple[int, int]:
    """Get table and figure counts with separate queries to avoid cartesian product."""
    table_count_result = await db.execute(
        select(func.count()).select_from(DocumentTable).where(DocumentTable.document_id == document_id)
    )
    figure_count_result = await db.execute(
        select(func.count()).select_from(DocumentFigure).where(DocumentFigure.document_id == document_id)
    )
    return table_count_result.scalar() or 0, figure_count_result.scalar() or 0


async def _extract_visuals_task(
    document_id: uuid.UUID,
    pdf_path: str,
    page_count: int,
    force: bool,
):
    """Background task for visual extraction."""
    from core.database import async_session_factory
    
    start_time = time.perf_counter()
    
    async with async_session_factory() as db:
        try:
            if force:
                await db.execute(
                    delete(DocumentTable).where(DocumentTable.document_id == document_id)
                )
                await db.execute(
                    delete(DocumentFigure).where(DocumentFigure.document_id == document_id)
                )
                await db.commit()
            
            tables_count = 0
            figures_count = 0
            errors = []
            pages_processed = 0
            
            async with httpx.AsyncClient(timeout=120.0) as http_client:
                for page_num in range(page_count):
                    try:
                        tables = await asyncio.to_thread(extract_tables_from_page, pdf_path, page_num)
                        for table in tables:
                            processed = process_extracted_table(table)
                            doc_table = DocumentTable(
                                document_id=document_id,
                                page_number=processed["page_number"],
                                title=processed["title"],
                                row_count=processed["row_count"],
                                column_count=processed["column_count"],
                                table_data=processed["table_data"],
                                markdown_repr=processed["markdown_repr"],
                            )
                            db.add(doc_table)
                            tables_count += 1
                        
                        figures = await analyze_figures_on_page(pdf_path, page_num, http_client)
                        for fig in figures:
                            doc_figure = DocumentFigure(
                                document_id=document_id,
                                page_number=fig.page_number,
                                figure_type=fig.figure_type,
                                description=fig.description,
                                extracted_data=fig.extracted_data,
                            )
                            db.add(doc_figure)
                            figures_count += 1
                            metrics.inc_counter(MetricNames.VISION_CALLS)
                        
                        pages_processed += 1
                        
                        if pages_processed % BATCH_COMMIT_SIZE == 0:
                            await db.commit()
                        
                    except Exception as e:
                        logger.error(f"Error processing page {page_num}: {e}")
                        errors.append({"page": page_num, "error": str(e)})
                        metrics.inc_counter(MetricNames.VISION_FAILURES)
                        await db.rollback()
            
            await db.commit()
            
            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_histogram(MetricNames.VISUAL_EXTRACTION_TIME_MS, duration_ms)
            metrics.inc_counter(MetricNames.TABLES_EXTRACTED, tables_count)
            metrics.inc_counter(MetricNames.FIGURES_EXTRACTED, figures_count)
            
            if errors:
                logger.warning(
                    f"Visual extraction had errors",
                    extra={"document_id": str(document_id), "error_count": len(errors)},
                )
            
            doc_result = await db.execute(select(Document).where(Document.id == document_id))
            document = doc_result.scalar_one_or_none()
            if document:
                document.visual_extraction_status = "completed" if not errors else "partial"
                document.visual_pages_processed = pages_processed
                document.visual_extraction_at = datetime.now(timezone.utc)
                await db.commit()
            
            logger.info(
                f"Visual extraction complete",
                extra={
                    "document_id": str(document_id),
                    "tables": tables_count,
                    "figures": figures_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            
        except Exception as e:
            logger.error(f"Visual extraction failed for {document_id}: {e}")
            await db.rollback()


@router.post(
    "/documents/{document_id}/extract-visuals",
    response_model=ExtractVisualsResponse,
    dependencies=[Depends(require_services_ready)],
)
async def extract_visuals(
    document_id: uuid.UUID,
    request: ExtractVisualsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ExtractVisualsResponse:
    """Extract tables and figures from a document."""
    set_document_id(str(document_id))
    set_phase("multimodal")
    
    logger.info(f"Visual extraction requested", extra={"force": request.force})
    
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = doc_result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    if document.status != "validated":
        raise HTTPException(status_code=400, detail="Document not validated")
    
    if not request.force:
        is_complete = (
            document.visual_extraction_status == "completed"
            and document.visual_pages_processed == document.page_count
        )
        
        if is_complete:
            table_count, figure_count = await _get_visual_counts(db, document_id)
            return ExtractVisualsResponse(
                document_id=document_id,
                tables_extracted=table_count,
                figures_extracted=figure_count,
                pages_processed=document.visual_pages_processed or 0,
                status="completed",
            )
        
        if document.visual_extraction_status == "partial":
            table_count, figure_count = await _get_visual_counts(db, document_id)
            return ExtractVisualsResponse(
                document_id=document_id,
                tables_extracted=table_count,
                figures_extracted=figure_count,
                pages_processed=document.visual_pages_processed or 0,
                status="partial",
            )
    
    stored_filename = generate_stored_filename(document_id)
    pdf_path = get_file_path(stored_filename)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")
    
    background_tasks.add_task(
        _extract_visuals_task,
        document_id,
        str(pdf_path),
        document.page_count or 0,
        request.force,
    )
    
    return ExtractVisualsResponse(
        document_id=document_id,
        tables_extracted=0,
        figures_extracted=0,
        pages_processed=0,
        status="processing",
    )


@router.get(
    "/documents/{document_id}/tables",
    response_model=list[TableData],
    dependencies=[Depends(require_services_ready)],
)
async def list_tables(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TableData]:
    """List all extracted tables for a document."""
    result = await db.execute(
        select(DocumentTable)
        .where(DocumentTable.document_id == document_id)
        .order_by(DocumentTable.page_number)
    )
    tables = result.scalars().all()
    
    return [
        TableData(
            id=t.id,
            page_number=t.page_number,
            title=t.title,
            row_count=t.row_count,
            column_count=t.column_count,
            markdown=t.markdown_repr,
        )
        for t in tables
    ]


@router.get(
    "/documents/{document_id}/figures",
    response_model=list[FigureData],
    dependencies=[Depends(require_services_ready)],
)
async def list_figures(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[FigureData]:
    """List all extracted figures for a document."""
    result = await db.execute(
        select(DocumentFigure)
        .where(DocumentFigure.document_id == document_id)
        .order_by(DocumentFigure.page_number)
    )
    figures = result.scalars().all()
    
    return [
        FigureData(
            id=f.id,
            page_number=f.page_number,
            figure_type=f.figure_type,
            description=f.description,
        )
        for f in figures
    ]
