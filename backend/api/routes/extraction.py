"""Text extraction API endpoints."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_services_ready
from core.database import get_db, async_session_maker
from models.document import Document, DocumentStatus
from models.document_page import DocumentPage
from schemas.document_page import (
    ExtractionResponse,
    ExtractionStatusResponse,
    DocumentPageDetail,
    DocumentPageSummary,
)
from services.text_extractor import extract_document_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["extraction"])


async def run_extraction_task(document_id: uuid.UUID, pdf_path: str) -> None:
    """Background task for text extraction."""
    async with async_session_maker() as db:
        try:
            await extract_document_text(document_id, pdf_path, db)
        except Exception as e:
            logger.error(f"Background extraction failed for {document_id}: {e}")


@router.post(
    "/{document_id}/extract-text",
    response_model=ExtractionResponse,
    dependencies=[Depends(require_services_ready)],
)
async def extract_text(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    sync: bool = False,
) -> ExtractionResponse:
    """
    Trigger text extraction for a document.
    
    By default runs in background. Set sync=true for synchronous extraction.
    """
    # Validate document exists
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    if not document.file_path:
        raise HTTPException(status_code=400, detail="Document has no file path")
    
    if document.status == DocumentStatus.FAILED:
        raise HTTPException(status_code=400, detail="Cannot extract from failed document")
    
    logger.info(f"Extraction requested for document {document_id}, sync={sync}")
    
    if sync:
        # Synchronous extraction (for testing or small documents)
        extraction_result = await extract_document_text(document_id, document.file_path, db)
        return ExtractionResponse(
            document_id=extraction_result.document_id,
            total_pages=extraction_result.total_pages,
            native_pages=extraction_result.native_pages,
            scanned_pages=extraction_result.scanned_pages,
            skipped_pages=extraction_result.skipped_pages,
            failed_pages=extraction_result.failed_pages,
            low_confidence_pages=extraction_result.low_confidence_pages,
            avg_confidence=extraction_result.avg_confidence,
            status=extraction_result.status,
        )
    
    # Get current extraction status for response
    existing_count = await db.execute(
        select(func.count()).select_from(DocumentPage).where(
            DocumentPage.document_id == document_id
        )
    )
    pages_extracted = existing_count.scalar() or 0
    
    # Queue background extraction
    background_tasks.add_task(run_extraction_task, document_id, document.file_path)
    
    return ExtractionResponse(
        document_id=document_id,
        total_pages=document.page_count or 0,
        native_pages=0,
        scanned_pages=0,
        skipped_pages=pages_extracted,
        failed_pages=0,
        status="processing",
    )


@router.get(
    "/{document_id}/extraction-status",
    response_model=ExtractionStatusResponse,
    dependencies=[Depends(require_services_ready)],
)
async def get_extraction_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ExtractionStatusResponse:
    """Get extraction status for a document."""
    # Validate document exists
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    # Count extracted pages
    count_result = await db.execute(
        select(func.count()).select_from(DocumentPage).where(
            DocumentPage.document_id == document_id
        )
    )
    pages_extracted = count_result.scalar() or 0
    
    total_pages = document.page_count or 0
    
    if pages_extracted == 0:
        status = "pending"
    elif pages_extracted < total_pages:
        status = "partial"
    else:
        status = "completed"
    
    return ExtractionStatusResponse(
        document_id=document_id,
        extraction_status=status,
        pages_extracted=pages_extracted,
        total_pages=total_pages,
    )


@router.get(
    "/{document_id}/pages",
    response_model=list[DocumentPageSummary],
    dependencies=[Depends(require_services_ready)],
)
async def list_document_pages(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentPageSummary]:
    """List all extracted pages for a document."""
    # Validate document exists
    doc_result = await db.execute(
        select(Document.id).where(Document.id == document_id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    pages = result.scalars().all()
    
    return [
        DocumentPageSummary(
            page_number=p.page_number,
            page_type=p.page_type,
            text_length=len(p.extracted_text),
            confidence=p.confidence,
        )
        for p in pages
    ]


@router.get(
    "/{document_id}/pages/{page_number}",
    response_model=DocumentPageDetail,
    dependencies=[Depends(require_services_ready)],
)
async def get_document_page(
    document_id: uuid.UUID,
    page_number: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentPageDetail:
    """Get extracted text for a specific page."""
    result = await db.execute(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
        )
    )
    page = result.scalar_one_or_none()
    
    if not page:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_number} not found for document {document_id}",
        )
    
    return DocumentPageDetail.model_validate(page)
