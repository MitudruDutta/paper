"""Document upload and management endpoints."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Annotated

import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_services_ready
from core.config import settings
from core.database import get_db
from core.storage import (
    delete_temp_file,
    save_temp_file,
    save_uploaded_file,
)
from models.document import Document, DocumentStatus
from schemas.document import (
    DocumentDetail,
    DocumentError,
    DocumentListItem,
    DocumentUploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {"application/pdf"}
MAX_UPLOAD_SIZE = settings.max_upload_size_mb * 1024 * 1024


def _validate_pdf_sync(file_path: Path) -> tuple[bool, str | None, int | None]:
    """Synchronous PDF validation (runs in executor)."""
    try:
        doc = fitz.open(str(file_path))
        
        if doc.is_encrypted:
            doc.close()
            return False, "Password-protected PDFs are not supported", None
        
        page_count = len(doc)
        if page_count == 0:
            doc.close()
            return False, "PDF file contains no pages", None
        
        doc.close()
        return True, None, page_count
        
    except fitz.FileDataError:
        return False, "Invalid or corrupted PDF file", None
    except Exception as e:
        logger.error(f"PDF validation error: {e}")
        return False, f"Failed to validate PDF: {str(e)}", None


async def validate_pdf_file(file_path: Path) -> tuple[bool, str | None, int | None]:
    """
    Validate PDF file integrity.
    
    Returns:
        Tuple of (is_valid, error_message, page_count)
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _validate_pdf_sync, file_path)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    responses={
        400: {"model": DocumentError},
        413: {"model": DocumentError},
        422: {"model": DocumentError},
    },
    dependencies=[Depends(require_services_ready)],
)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF file to upload")],
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload and validate a PDF document.
    
    - Accepts only PDF files
    - Maximum file size: 50 MB
    - Rejects password-protected or corrupted PDFs
    """
    document_id = uuid.uuid4()
    temp_path: Path | None = None
    
    logger.info(f"Upload started: {file.filename}, content_type={file.content_type}")
    
    try:
        # Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"Invalid MIME type: {file.content_type}")
            raise HTTPException(
                status_code=400,
                detail="Invalid file type: only PDF files are accepted",
            )
        
        # Save to temp location with streaming and size check
        try:
            temp_path = await save_temp_file(file, MAX_UPLOAD_SIZE, suffix=".pdf")
            logger.info(f"Saved temp file: {temp_path}")
        except ValueError as e:
            logger.warning(f"File too large: {e}")
            raise HTTPException(
                status_code=413,
                detail=f"File too large: maximum size is {settings.max_upload_size_mb} MB",
            )
        
        # Get actual file size from the saved temp file
        file_size = temp_path.stat().st_size
        
        if file_size == 0:
            await delete_temp_file(temp_path)
            raise HTTPException(
                status_code=400,
                detail="Empty file: uploaded file contains no data",
            )
        
        # Validate PDF integrity
        is_valid, error_msg, page_count = await validate_pdf_file(temp_path)
        
        if not is_valid:
            logger.warning(f"PDF validation failed: {error_msg}")
            await delete_temp_file(temp_path)
            
            # Create failed document record
            document = Document(
                id=document_id,
                filename=file.filename or "unknown.pdf",
                file_size=file_size,
                mime_type=file.content_type,
                status=DocumentStatus.FAILED,
                error_message=error_msg,
            )
            db.add(document)
            await db.commit()
            
            raise HTTPException(
                status_code=422,
                detail=f"Invalid PDF file: {error_msg}",
            )
        
        # Move to permanent storage
        stored_filename, file_path = await save_uploaded_file(temp_path, document_id)
        temp_path = None  # File moved, don't delete in finally
        
        logger.info(f"File stored: {stored_filename}")
        
        # Create document record
        document = Document(
            id=document_id,
            filename=file.filename or "unknown.pdf",
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=file.content_type,
            page_count=page_count,
            status=DocumentStatus.VALIDATED,
        )
        db.add(document)
        await db.commit()
        
        logger.info(f"Document created: {document_id}, status={DocumentStatus.VALIDATED.value}")
        
        return DocumentUploadResponse(
            document_id=document_id,
            filename=document.filename,
            status=document.status.value,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        if temp_path:
            await delete_temp_file(temp_path)
        raise HTTPException(
            status_code=500,
            detail="Upload failed: an unexpected error occurred",
        )


@router.get(
    "",
    response_model=list[DocumentListItem],
    dependencies=[Depends(require_services_ready)],
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
) -> list[DocumentListItem]:
    """List all uploaded documents, ordered by creation date (newest first)."""
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    return [DocumentListItem.model_validate(doc) for doc in documents]


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    responses={404: {"model": DocumentError}},
    dependencies=[Depends(require_services_ready)],
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentDetail:
    """Get full metadata for a specific document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: no document with ID {document_id}",
        )
    
    return DocumentDetail.model_validate(document)


@router.get(
    "/{document_id}/pdf",
    responses={404: {"model": DocumentError}, 403: {"model": DocumentError}},
    dependencies=[Depends(require_services_ready)],
)
async def get_document_pdf(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the PDF file for viewing."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.file_path:
        raise HTTPException(status_code=404, detail="PDF file not available")
    
    file_path = Path(document.file_path)
    
    # Validate path is within expected storage root to prevent traversal
    storage_root = Path(settings.document_storage_path).resolve()
    try:
        resolved_path = file_path.resolve()
        # Use is_relative_to for robust path containment check
        if not resolved_path.is_relative_to(storage_root):
            raise HTTPException(status_code=403, detail="Access denied")
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=403, detail="Invalid file path")
    
    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    return FileResponse(
        path=resolved_path,
        media_type="application/pdf",
        filename=document.filename,
    )
