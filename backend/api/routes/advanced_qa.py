"""Advanced QA API endpoints (Phase 5)."""

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from qdrant_client import QdrantClient
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError, DataError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_services_ready, get_qdrant
from core.database import get_db
from core.concurrency import with_llm_limit_or_reject, QueueFullError
from core.logging import set_phase
from core.metrics import metrics, MetricNames
from models.document import Document
from models.document_chunk import DocumentChunk
from schemas.advanced_qa import (
    AdvancedQuestionRequest,
    AdvancedAnswerResponse,
    DocumentSource,
)
from services.conversation_manager import (
    get_or_create_conversation,
    resolve_followup,
    add_message,
)
from services.multi_doc_qa import retrieve_from_documents, generate_multi_doc_answer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["advanced-qa"])


@router.post(
    "/ask",
    response_model=AdvancedAnswerResponse,
    dependencies=[Depends(require_services_ready)],
)
async def ask_advanced(
    request: AdvancedQuestionRequest,
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
) -> AdvancedAnswerResponse:
    """
    Ask a question across one or more documents with conversation support.
    
    Supports:
    - Multi-document queries
    - Follow-up questions with coreference resolution
    - Confidence scoring
    """
    set_phase("qa")
    start_time = time.perf_counter()
    
    logger.info(
        f"Advanced QA request",
        extra={"docs": len(request.document_ids), "conversation": str(request.conversation_id)[:8] if request.conversation_id else None},
    )
    
    # Validate all documents exist and are indexed
    doc_result = await db.execute(
        select(Document).where(Document.id.in_(request.document_ids))
    )
    documents = {d.id: d for d in doc_result.scalars().all()}
    
    missing = [str(d) for d in request.document_ids if d not in documents]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Documents not found: {', '.join(missing)}",
        )
    
    # Check all documents are indexed
    chunk_counts = await db.execute(
        select(DocumentChunk.document_id, func.count())
        .where(DocumentChunk.document_id.in_(request.document_ids))
        .group_by(DocumentChunk.document_id)
    )
    indexed_docs = {row[0] for row in chunk_counts.all()}
    
    not_indexed = [str(d) for d in request.document_ids if d not in indexed_docs]
    if not_indexed:
        raise HTTPException(
            status_code=400,
            detail=f"Documents not indexed: {', '.join(not_indexed)}. Run indexing first.",
        )
    
    # Get or create conversation
    conversation, is_new = await get_or_create_conversation(db, request.conversation_id)
    
    # Resolve follow-up references
    context = await resolve_followup(request.question, conversation)
    effective_question = context.rewritten_question
    
    if context.needs_rewrite:
        logger.info(f"Resolved follow-up", extra={"original": request.question[:50], "resolved": effective_question[:50]})
    
    # Store user message
    await add_message(
        db, conversation, "user", request.question,
        document_ids=request.document_ids,
    )
    
    conversation_persisted = True
    retrieval_start = time.perf_counter()
    
    # Retrieve from all documents
    retrieval = await retrieve_from_documents(
        qdrant,
        effective_question,
        request.document_ids,
        db,
    )
    retrieval_time_ms = (time.perf_counter() - retrieval_start) * 1000
    
    # Generate answer with concurrency limit
    llm_start = time.perf_counter()
    try:
        async def _generate():
            return await generate_multi_doc_answer(
                effective_question,
                retrieval,
            )
            
        qa_result = await with_llm_limit_or_reject(_generate(), timeout=45.0)
        metrics.inc_counter(MetricNames.LLM_CALLS)
    except QueueFullError:
        metrics.inc_counter(MetricNames.QA_FAILURE)
        raise HTTPException(
            status_code=503,
            detail="Server busy. Please try again in a few seconds.",
            headers={"Retry-After": "15"},
        )
    llm_time_ms = (time.perf_counter() - llm_start) * 1000
    
    if not qa_result.success:
        logger.error(f"Multi-doc QA failed: {qa_result.error}", extra={"error_type": "llm_failure"})
        metrics.inc_counter(MetricNames.QA_FAILURE)
        metrics.inc_counter(MetricNames.LLM_FAILURES)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate answer. Please try again.",
        )
    
    # Store assistant message
    try:
        await add_message(
            db, conversation, "assistant", qa_result.answer,
            cited_pages=qa_result.cited_pages,
            document_ids=request.document_ids,
        )
        await db.commit()
    except (IntegrityError, DataError, OperationalError) as e:
        logger.error(f"Failed to store conversation: {type(e).__name__}: {e}")
        await db.rollback()
        conversation_persisted = False
    except Exception as e:
        logger.error(f"Unexpected error storing conversation: {e}")
        await db.rollback()
        conversation_persisted = False
    
    # Build response
    sources = [
        DocumentSource(
            document_id=s.document_id,
            document_name=s.document_name,
            page_start=s.page_start,
            page_end=s.page_end,
            chunk_id=s.chunk_id,
        )
        for s in qa_result.sources
    ]
    
    # Record metrics
    total_time_ms = (time.perf_counter() - start_time) * 1000
    metrics.record_histogram(MetricNames.QA_TIME_MS, total_time_ms)
    metrics.record_histogram(MetricNames.QA_RETRIEVAL_TIME_MS, retrieval_time_ms)
    metrics.record_histogram(MetricNames.QA_LLM_TIME_MS, llm_time_ms)
    metrics.record_histogram(MetricNames.QA_CITATIONS, len(qa_result.cited_pages))
    metrics.record_histogram(MetricNames.QA_CONFIDENCE, qa_result.confidence)
    metrics.inc_counter(MetricNames.QA_SUCCESS)
    
    if qa_result.required_regeneration:
        metrics.inc_counter(MetricNames.QA_REGENERATIONS)
    
    logger.info(
        f"Advanced QA complete",
        extra={
            "duration_ms": round(total_time_ms, 2),
            "confidence": qa_result.confidence,
            "sources": len(sources),
            "persisted": conversation_persisted,
        },
    )
    
    return AdvancedAnswerResponse(
        answer=qa_result.answer,
        confidence=qa_result.confidence,
        sources=sources,
        conversation_id=conversation.id,
        conversation_persisted=conversation_persisted,
    )
