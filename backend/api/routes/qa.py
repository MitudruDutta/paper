"""Question-answering API endpoints."""

import hashlib
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from qdrant_client import QdrantClient
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, retry_if_exception_type, before_sleep_log

from api.dependencies import require_services_ready, get_qdrant
from core.database import get_db
from core.concurrency import with_llm_limit_or_reject, QueueFullError
from models.document import Document
from models.document_chunk import DocumentChunk
from models.qa_query import QAQuery
from schemas.qa import QuestionRequest, AnswerResponse, SourceInfo
from services.prompt_builder import ChunkContext
from services.qa_engine import answer_question
from services.retriever import search_similar

logger = logging.getLogger(__name__)

router = APIRouter(tags=["qa"])

RETRIEVAL_TOP_K = 8  # Retrieve more, then filter by relevance


@retry(
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(OperationalError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _store_qa_audit(db: AsyncSession, qa_query: QAQuery) -> None:
    """Store QA query with retry on transient DB errors. Idempotent via unique key."""
    try:
        db.add(qa_query)
        await db.commit()
    except IntegrityError:
        # Duplicate key - already stored, treat as success
        await db.rollback()
        logger.info(f"QA audit already exists for idempotency_key={qa_query.idempotency_key[:16]}...")
    except OperationalError:
        await db.rollback()
        raise


@router.post(
    "/documents/{document_id}/ask",
    response_model=AnswerResponse,
    dependencies=[Depends(require_services_ready)],
)
async def ask_question(
    document_id: uuid.UUID,
    request: QuestionRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
) -> AnswerResponse:
    """
    Ask a question about a document.
    
    Returns an answer with page-level citations, or a refusal if
    the information is not found in the document.
    """
    question_hash = hashlib.sha256(request.question.encode()).hexdigest()[:32]
    logger.info(f"Question received for document {document_id}, hash={question_hash}, len={len(request.question)}")
    
    # Validate document exists
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = doc_result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    # Check document is indexed
    chunk_count = await db.execute(
        select(func.count()).select_from(DocumentChunk).where(
            DocumentChunk.document_id == document_id
        )
    )
    if (chunk_count.scalar() or 0) == 0:
        raise HTTPException(
            status_code=400,
            detail="Document not indexed. Run indexing first.",
        )
    
    # Retrieve relevant chunks (this is fast, no limit needed)
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        search_results = await search_similar(
            qdrant,
            request.question,
            document_ids=[document_id],
            top_k=RETRIEVAL_TOP_K,
            http_client=http_client,
        )
    
    logger.info(f"Retrieved {len(search_results)} chunks")
    
    if not search_results:
        logger.warning("No chunks retrieved for question")
        return AnswerResponse(
            answer="I cannot find this information in the provided document.",
            sources=[],
        )
    
    # Fetch chunk content from database
    chunk_ids = [r[0] for r in search_results]
    chunks_result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
    )
    chunk_map = {c.id: c for c in chunks_result.scalars().all()}
    
    # Build ChunkContext list preserving search order
    chunks: list[ChunkContext] = []
    for chunk_id, score, payload in search_results:
        chunk = chunk_map.get(chunk_id)
        if chunk:
            chunks.append(ChunkContext(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
            ))
    
    # Generate answer (with concurrency limit)
    try:
        async def _generate():
            async with httpx.AsyncClient(timeout=120.0) as http_client:
                return await answer_question(request.question, chunks, http_client)
        
        qa_result = await with_llm_limit_or_reject(_generate(), timeout=30.0)
    except QueueFullError:
        raise HTTPException(
            status_code=503,
            detail="Server busy with other requests. Please try again in a few seconds.",
            headers={"Retry-After": "10"},
        )
    
    if not qa_result.success:
        logger.error(f"QA failed: {qa_result.error}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate answer. Please try again.",
        )
    
    # Store QA in audit trail
    try:
        idempotency_key = QAQuery.generate_idempotency_key(
            document_id, request.question, qa_result.answer
        )
        qa_query = QAQuery(
            document_id=document_id,
            idempotency_key=idempotency_key,
            question=request.question,
            answer=qa_result.answer,
            cited_pages=qa_result.cited_pages,
        )
        await _store_qa_audit(db, qa_query)
        logger.info(f"Stored QA query with cited pages: {qa_result.cited_pages}")
    except (DataError, OperationalError) as e:
        logger.error(f"DB error storing QA audit trail: {type(e).__name__}: {e}, cited_pages={qa_result.cited_pages}")
        await db.rollback()
    except Exception as e:
        logger.error(f"Unexpected error storing QA audit trail: {type(e).__name__}: {e}, cited_pages={qa_result.cited_pages}")
        await db.rollback()
    
    # Build response
    sources = [
        SourceInfo(
            page_start=s.page_start,
            page_end=s.page_end,
            chunk_id=s.chunk_id,
        )
        for s in qa_result.sources
    ]
    
    # Determine confidence based on citation coverage
    if not qa_result.cited_pages:
        confidence = "low"  # No citations (refusal or issue)
    elif len(qa_result.cited_pages) >= 3:
        confidence = "high"  # Multiple sources
    elif len(qa_result.sources) >= 2:
        confidence = "high"  # Multiple chunks cited
    else:
        confidence = "medium"  # Single source
    
    logger.info(f"Returning answer with {len(sources)} sources, confidence={confidence}")
    
    return AnswerResponse(
        answer=qa_result.answer,
        sources=sources,
        confidence=confidence,
    )
