"""Text extraction service for PDF documents."""

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.document_page import DocumentPage, PageType
from utils.ocr_utils import ocr_pdf_page, MIN_OCR_CONFIDENCE

logger = logging.getLogger(__name__)

# Minimum characters to consider a page as having native text
NATIVE_TEXT_THRESHOLD = 50
# Minimum characters to accept native text even if below threshold (avoid OCR on sparse pages)
MIN_NATIVE_TEXT = 10
# Batch size for page extraction (balance between PDF open overhead and memory)
EXTRACTION_BATCH_SIZE = 10


@dataclass
class PageResult:
    """Result of extracting text from a single page."""
    page_number: int
    page_type: PageType
    text: str
    confidence: float | None
    success: bool
    error: str | None = None


@dataclass
class ExtractionResult:
    """Result of extracting text from entire document."""
    document_id: uuid.UUID
    total_pages: int
    native_pages: int
    scanned_pages: int
    skipped_pages: int
    failed_pages: int
    low_confidence_pages: int
    avg_confidence: float | None
    status: str


def normalize_text(text: str) -> str:
    """Normalize extracted text."""
    # Fix hyphenated line breaks
    text = re.sub(r"-\s*\n\s*", "", text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_native_text(page: fitz.Page) -> str:
    """Extract text from a native PDF page using PyMuPDF."""
    blocks = page.get_text("dict")["blocks"]
    lines = []
    
    for block in blocks:
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                line_text = ""
                for span in line.get("spans", []):
                    line_text += span.get("text", "")
                if line_text.strip():
                    lines.append(line_text.strip())
    
    return normalize_text("\n".join(lines))


def classify_and_extract(page: fitz.Page, pdf_path: str, page_number: int) -> PageResult:
    """
    Classify a page and extract text appropriately.
    
    Strategy:
    1. Try native extraction first
    2. If native text >= threshold: use native
    3. If native text < threshold but >= MIN_NATIVE_TEXT: try OCR, fallback to native
    4. If native text < MIN_NATIVE_TEXT: must use OCR
    """
    native_text = extract_native_text(page)
    native_len = len(native_text)
    
    # Good native text - use it
    if native_len >= NATIVE_TEXT_THRESHOLD:
        return PageResult(
            page_number=page_number,
            page_type=PageType.NATIVE,
            text=native_text,
            confidence=1.0,
            success=True,
        )
    
    # Some native text exists - try OCR but can fallback
    if native_len >= MIN_NATIVE_TEXT:
        try:
            ocr_text, ocr_confidence = ocr_pdf_page(pdf_path, page_number)
            
            # Use OCR if it's good, otherwise use native text
            if ocr_text and ocr_confidence >= MIN_OCR_CONFIDENCE:
                return PageResult(
                    page_number=page_number,
                    page_type=PageType.SCANNED,
                    text=ocr_text,
                    confidence=ocr_confidence,
                    success=True,
                )
        except Exception as e:
            logger.warning(f"OCR failed for page {page_number}, using native text: {e}")
        
        # Fallback to native text
        return PageResult(
            page_number=page_number,
            page_type=PageType.NATIVE,
            text=native_text,
            confidence=1.0,
            success=True,
        )
    
    # Very little/no native text - must OCR
    try:
        ocr_text, ocr_confidence = ocr_pdf_page(pdf_path, page_number)
        
        if ocr_text and ocr_confidence >= MIN_OCR_CONFIDENCE:
            return PageResult(
                page_number=page_number,
                page_type=PageType.SCANNED,
                text=ocr_text,
                confidence=ocr_confidence,
                success=True,
            )
        
        # OCR failed but we have some native text - use it anyway
        if native_text:
            return PageResult(
                page_number=page_number,
                page_type=PageType.NATIVE,
                text=native_text,
                confidence=1.0,
                success=True,
            )
        
        return PageResult(
            page_number=page_number,
            page_type=PageType.SCANNED,
            text="",
            confidence=ocr_confidence,
            success=False,
            error=f"OCR confidence too low ({ocr_confidence:.2f}) and no native text",
        )
        
    except Exception as e:
        # OCR failed completely - use native if available
        if native_text:
            return PageResult(
                page_number=page_number,
                page_type=PageType.NATIVE,
                text=native_text,
                confidence=1.0,
                success=True,
            )
        
        return PageResult(
            page_number=page_number,
            page_type=PageType.SCANNED,
            text="",
            confidence=None,
            success=False,
            error=str(e),
        )


def extract_page_sync(pdf_path: str, page_number: int) -> PageResult:
    """
    Extract text from a single page (synchronous, thread-safe).
    Opens and closes the PDF document within this function.
    """
    try:
        with fitz.open(pdf_path) as doc:
            page = doc[page_number]
            return classify_and_extract(page, pdf_path, page_number)
    except Exception as e:
        logger.error(f"Failed to extract page {page_number}: {e}")
        return PageResult(
            page_number=page_number,
            page_type=PageType.SCANNED,
            text="",
            confidence=None,
            success=False,
            error=str(e),
        )


def extract_pages_batch(pdf_path: str, page_numbers: list[int]) -> list[PageResult]:
    """
    Extract text from multiple pages in a single batch (thread-safe).
    Opens the PDF once for the entire batch.
    """
    results = []
    try:
        with fitz.open(pdf_path) as doc:
            for page_num in page_numbers:
                try:
                    page = doc[page_num]
                    result = classify_and_extract(page, pdf_path, page_num)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to extract page {page_num}: {e}")
                    results.append(PageResult(
                        page_number=page_num,
                        page_type=PageType.SCANNED,
                        text="",
                        confidence=None,
                        success=False,
                        error=str(e),
                    ))
    except Exception as e:
        # Document open failed - return errors for all pages
        logger.error(f"Failed to open PDF for batch: {e}")
        for page_num in page_numbers:
            results.append(PageResult(
                page_number=page_num,
                page_type=PageType.SCANNED,
                text="",
                confidence=None,
                success=False,
                error=str(e),
            ))
    return results


async def extract_document_text(
    document_id: uuid.UUID,
    pdf_path: str,
    db: AsyncSession,
) -> ExtractionResult:
    """
    Extract text from all pages of a document.
    """
    logger.info(f"Starting extraction for document {document_id}")
    
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Check which pages already exist (for idempotency)
    existing = await db.execute(
        select(DocumentPage.page_number).where(DocumentPage.document_id == document_id)
    )
    existing_pages = {row[0] for row in existing.fetchall()}
    
    loop = asyncio.get_running_loop()
    
    native_count = 0
    scanned_count = 0
    skipped_count = len(existing_pages)
    failed_count = 0
    low_confidence_count = 0
    confidences = []
    
    # Get total pages (quick open/close)
    with fitz.open(str(path)) as doc:
        total_pages = len(doc)
    
    # Filter pages to extract
    pages_to_extract = [p for p in range(total_pages) if p not in existing_pages]
    
    # Process in batches
    for batch_start in range(0, len(pages_to_extract), EXTRACTION_BATCH_SIZE):
        batch_pages = pages_to_extract[batch_start:batch_start + EXTRACTION_BATCH_SIZE]
        
        # Run batch extraction in executor
        batch_results = await loop.run_in_executor(
            None, extract_pages_batch, str(path), batch_pages
        )
        
        # Process results for this batch
        try:
            batch_native = 0
            batch_scanned = 0
            rows_to_insert = []
            
            for result in batch_results:
                if not result.success:
                    logger.warning(f"Page {result.page_number} extraction failed: {result.error}")
                    failed_count += 1
                    continue
                
                rows_to_insert.append({
                    "document_id": document_id,
                    "page_number": result.page_number,
                    "page_type": result.page_type.value,
                    "extracted_text": result.text,
                    "confidence": result.confidence,
                })
                
                if result.page_type == PageType.NATIVE:
                    batch_native += 1
                else:
                    batch_scanned += 1
                    if result.confidence is not None:
                        confidences.append(result.confidence)
                        if result.confidence < 0.7:
                            low_confidence_count += 1
                
                logger.debug(
                    f"Page {result.page_number}: {result.page_type.value}, "
                    f"confidence={result.confidence}, chars={len(result.text)}"
                )
            
            # Bulk insert all pages in batch
            if rows_to_insert:
                stmt = insert(DocumentPage).values(rows_to_insert).on_conflict_do_nothing(
                    index_elements=["document_id", "page_number"]
                )
                await db.execute(stmt)
                await db.commit()
            
            # Update global counts only after successful commit
            native_count += batch_native
            scanned_count += batch_scanned
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Batch commit failed for document {document_id}: {e}")
            raise
    
    status = "completed"
    if failed_count == total_pages:
        status = "failed"
    elif failed_count > 0:
        status = "partial"
    
    logger.info(
        f"Extraction complete for {document_id}: "
        f"native={native_count}, scanned={scanned_count}, "
        f"skipped={skipped_count}, failed={failed_count}, low_conf={low_confidence_count}"
    )
    
    avg_conf = sum(confidences) / len(confidences) if confidences else None
    
    return ExtractionResult(
        document_id=document_id,
        total_pages=total_pages,
        native_pages=native_count,
        scanned_pages=scanned_count,
        skipped_pages=skipped_count,
        failed_pages=failed_count,
        low_confidence_pages=low_confidence_count,
        avg_confidence=round(avg_conf, 3) if avg_conf else None,
        status=status,
    )
