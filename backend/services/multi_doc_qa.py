"""Multi-document QA service."""

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field

from qdrant_client import QdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import Document
from models.document_chunk import DocumentChunk
from models.document_figure import DocumentFigure
from services.prompt_builder import ChunkContext
from services.retriever import search_similar
from services.citation_validator import validate_and_fix_citations, extract_citations
from services.confidence_scorer import compute_confidence, ConfidenceInputs
from services.embedder import generate_embedding

logger = logging.getLogger(__name__)

RETRIEVAL_TOP_K_PER_DOC = 10
FIGURE_DEFAULT_SCORE = 0.7


@dataclass
class DocumentChunkContext(ChunkContext):
    """Chunk context with document attribution."""
    document_name: str = ""
    is_figure: bool = False
    figure_id: uuid.UUID | None = None


@dataclass
class MultiDocRetrievalResult:
    """Result of multi-document retrieval."""
    chunks_by_doc: dict[uuid.UUID, list[DocumentChunkContext]]
    scores_by_doc: dict[uuid.UUID, list[float]]
    doc_names: dict[uuid.UUID, str]


@dataclass
class MultiDocQAResult:
    """Result of multi-document QA."""
    answer: str
    sources: list[DocumentChunkContext]
    cited_pages: list[int]
    confidence: float
    success: bool
    error: str | None = None
    required_regeneration: bool = False


async def retrieve_from_documents(
    qdrant: QdrantClient,
    question: str,
    document_ids: list[uuid.UUID],
    db: AsyncSession,
) -> MultiDocRetrievalResult:
    """Retrieve relevant chunks from multiple documents in parallel."""
    # Get document names
    doc_result = await db.execute(
        select(Document).where(Document.id.in_(document_ids))
    )
    documents = {d.id: d for d in doc_result.scalars().all()}
    doc_names = {d_id: documents[d_id].filename if d_id in documents else "Unknown" 
                 for d_id in document_ids}
    
    # Check if question is about images/figures/pictures using word boundaries
    def is_likely_image_question(q: str) -> bool:
        q_lower = q.lower()
        # Check exclusions first to short-circuit false positives
        exclusions = r'\b(figure out|figure it|figures out)\b'
        if re.search(exclusions, q_lower):
            return False
        # Exact phrase patterns with word boundaries
        phrases = [r'\bshow image', r'\bshow figure', r'\bshow picture', r'\bshow visual',
                   r'\bwhat does it depict\b', r'\bvisualize this\b', r'\bdoes this image\b']
        if any(re.search(p, q_lower) for p in phrases):
            return True
        # Word boundary check for keywords
        keywords = r'\b(image|images|picture|pictures|figure|figures|photo|photos|diagram|chart|visual|visuals)\b'
        return bool(re.search(keywords, q_lower))
    
    is_image_question = is_likely_image_question(question)
    
    # Parallel retrieval per document with error handling that preserves doc_id
    async def retrieve_single(doc_id: uuid.UUID):
        try:
            results = await search_similar(
                qdrant,
                question,
                document_ids=[doc_id],
                top_k=RETRIEVAL_TOP_K_PER_DOC,
            )
            return doc_id, results, None
        except Exception as e:
            return doc_id, None, e
    
    retrieval_tasks = [retrieve_single(doc_id) for doc_id in document_ids]
    retrieval_results = await asyncio.gather(*retrieval_tasks)
    
    # Collect chunk IDs for DB fetch, handling failures
    all_chunk_ids = []
    results_map = {}
    for doc_id, results, error in retrieval_results:
        if error is not None:
            logger.error(f"Retrieval failed for document {doc_id}: {error}")
            continue
        results_map[doc_id] = results
        all_chunk_ids.extend([r[0] for r in results])
    
    # Fetch chunk content
    if all_chunk_ids:
        chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(all_chunk_ids))
        )
        chunk_map = {c.id: c for c in chunks_result.scalars().all()}
    else:
        chunk_map = {}
    
    # If image question, also fetch figure descriptions
    figure_chunks: dict[uuid.UUID, list[DocumentChunkContext]] = {}
    if is_image_question:
        figures_result = await db.execute(
            select(DocumentFigure).where(DocumentFigure.document_id.in_(document_ids))
        )
        figures = figures_result.scalars().all()
        
        for fig in figures:
            doc_id = fig.document_id
            if doc_id not in figure_chunks:
                figure_chunks[doc_id] = []
            
            # Create a synthetic chunk for the figure with distinct ID
            synthetic_chunk_id = uuid.uuid4()
            figure_chunks[doc_id].append(DocumentChunkContext(
                chunk_id=synthetic_chunk_id,
                document_id=doc_id,
                content=f"[Figure on Page {fig.page_number}] Type: {fig.figure_type}. {fig.description}",
                page_start=fig.page_number,
                page_end=fig.page_number,
                document_name=doc_names.get(doc_id, "Unknown"),
                is_figure=True,
                figure_id=fig.id,
            ))
        
        if not figures:
            logger.info("No extracted figures found - user should run Extract Tables/Figures first")
    
    # Build structured result
    chunks_by_doc: dict[uuid.UUID, list[DocumentChunkContext]] = {}
    scores_by_doc: dict[uuid.UUID, list[float]] = {}
    
    for doc_id, results in results_map.items():
        chunks_by_doc[doc_id] = []
        scores_by_doc[doc_id] = []
        
        for chunk_id, score, _ in results:
            chunk = chunk_map.get(chunk_id)
            if chunk:
                chunks_by_doc[doc_id].append(DocumentChunkContext(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    document_name=doc_names.get(doc_id, "Unknown"),
                ))
                scores_by_doc[doc_id].append(score)
    
    # Add figure chunks if available (for image-related questions)
    if figure_chunks:
        try:
            from services.embedder import generate_query_embedding
            question_embedding = await generate_query_embedding(question)
        except Exception as e:
            logger.warning(f"Failed to generate question embedding for figure scoring: {e}")
            question_embedding = None
        
        for doc_id, fig_chunks in figure_chunks.items():
            if doc_id not in chunks_by_doc:
                chunks_by_doc[doc_id] = []
                scores_by_doc[doc_id] = []
            chunks_by_doc[doc_id].extend(fig_chunks)
            
            if question_embedding is None:
                scores_by_doc[doc_id].extend([FIGURE_DEFAULT_SCORE] * len(fig_chunks))
                continue
            
            # Generate figure embeddings concurrently
            async def get_fig_embedding(content: str):
                try:
                    return await generate_embedding(content)
                except Exception:
                    return None
            
            embedding_results = await asyncio.gather(
                *[get_fig_embedding(fc.content) for fc in fig_chunks]
            )
            
            # Compute similarity scores
            norm_q = sum(a * a for a in question_embedding) ** 0.5
            fig_scores = []
            for fig_embedding in embedding_results:
                if fig_embedding and norm_q > 0:
                    dot = sum(a * b for a, b in zip(question_embedding, fig_embedding))
                    norm_f = sum(a * a for a in fig_embedding) ** 0.5
                    if norm_f > 0:
                        similarity = dot / (norm_q * norm_f)
                        fig_scores.append(max(0.0, min(1.0, similarity)))
                    else:
                        fig_scores.append(FIGURE_DEFAULT_SCORE)
                else:
                    fig_scores.append(FIGURE_DEFAULT_SCORE)
            
            scores_by_doc[doc_id].extend(fig_scores)
    
    logger.info(f"Retrieved chunks from {len(document_ids)} documents: " + 
                ", ".join(f"{doc_names.get(d, d)}: {len(chunks_by_doc.get(d, []))}" for d in document_ids))
    
    return MultiDocRetrievalResult(
        chunks_by_doc=chunks_by_doc,
        scores_by_doc=scores_by_doc,
        doc_names=doc_names,
    )


def build_multi_doc_context(retrieval: MultiDocRetrievalResult) -> tuple[str, list[DocumentChunkContext], set[int]]:
    """Build context string with clear document boundaries."""
    context_parts = []
    all_chunks = []
    valid_pages = set()
    
    for doc_id, chunks in retrieval.chunks_by_doc.items():
        doc_name = retrieval.doc_names.get(doc_id, "Unknown")
        
        for chunk in chunks:
            page_range = f"{chunk.page_start}" if chunk.page_start == chunk.page_end else f"{chunk.page_start}-{chunk.page_end}"
            context_parts.append(
                f"[Document: {doc_name} | Pages {page_range}]\n{chunk.content}"
            )
            all_chunks.append(chunk)
            for p in range(chunk.page_start, chunk.page_end + 1):
                valid_pages.add(p)
    
    return "\n\n".join(context_parts), all_chunks, valid_pages


def build_multi_doc_prompt(question: str, context: str, doc_names: dict[uuid.UUID, str], valid_pages: set[int]) -> list[dict]:
    """Build prompt for multi-document QA."""
    doc_list = ", ".join(doc_names.values())
    pages_list = sorted(valid_pages)
    num_docs = len(doc_names)
    
    if num_docs == 1:
        # Single document - simpler format
        doc_name = list(doc_names.values())[0]
        system_prompt = f"""You are a document analysis assistant. Answer questions using ONLY the provided context.

DOCUMENT: {doc_name}
VALID PAGES: {pages_list}

RULES:
1. Every factual claim MUST have a citation [Page X] or [Pages X-Y]
2. ONLY cite pages from the VALID PAGES list above
3. If information is not in the context, say "I cannot find this information in the provided document." with NO citation
4. Be concise and direct."""
    else:
        # Multiple documents - structured comparison format
        # Build dynamic format for N documents
        doc_format_lines = []
        for doc_name in doc_names.values():
            doc_format_lines.append(f"{doc_name}:\n- Finding... [Page X]")
        doc_format = "\n\n".join(doc_format_lines)
        
        system_prompt = f"""You are a document analysis assistant. Answer questions using ONLY the provided context from multiple documents.

DOCUMENTS: {doc_list}
VALID PAGES: {pages_list}

RULES:
1. Every factual claim MUST have a citation [Page X] or [Pages X-Y]
2. ONLY cite pages from the VALID PAGES list above
3. When comparing documents, structure your answer clearly:
   - State findings from each document separately with citations
   - Then provide synthesis/comparison citing both sources
4. If information is not in the context, say "I cannot find this information in the provided documents." with NO citation
5. If documents have conflicting information, acknowledge the conflict and cite both.

ANSWER FORMAT FOR COMPARISONS:
{doc_format}

Comparison:
- Synthesis citing relevant pages [Pages X, Y]"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]


async def generate_multi_doc_answer(
    question: str,
    retrieval: MultiDocRetrievalResult,
) -> MultiDocQAResult:
    """Generate answer for multi-document query."""
    from services.llm_client import generate_answer as llm_generate
    
    # Check if we have any chunks
    total_chunks = sum(len(chunks) for chunks in retrieval.chunks_by_doc.values())
    if total_chunks == 0:
        return MultiDocQAResult(
            answer="I cannot find relevant information in the provided documents.",
            sources=[],
            cited_pages=[],
            confidence=0.0,
            success=True,
        )
    
    # Build context and prompt
    context, all_chunks, valid_pages = build_multi_doc_context(retrieval)
    messages = build_multi_doc_prompt(question, context, retrieval.doc_names, valid_pages)
    
    # Get all retrieval scores
    all_scores = []
    for scores in retrieval.scores_by_doc.values():
        all_scores.extend(scores)
    
    required_regeneration = False
    max_retries = 2
    
    for attempt in range(max_retries + 1):
        logger.info(f"Multi-doc generation attempt {attempt + 1}/{max_retries + 1}")
        
        answer_text, model_used, success, error = await llm_generate(messages)
        
        if not success:
            logger.error(f"Generation failed on attempt {attempt + 1}/{max_retries + 1}: {error}")
            continue
        
        # Validate citations (reuse Phase 4 validator)
        # Convert to ChunkContext for validator
        chunk_contexts = [
            ChunkContext(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                content=c.content,
                page_start=c.page_start,
                page_end=c.page_end,
            )
            for c in all_chunks
        ]
        
        validation = validate_and_fix_citations(answer_text, chunk_contexts)
        
        if validation.valid:
            # Find which chunks were actually cited
            cited_chunks = [
                c for c in all_chunks
                if any(p in validation.cited_pages for p in range(c.page_start, c.page_end + 1))
            ]
            
            # Compute confidence
            confidence = compute_confidence(ConfidenceInputs(
                retrieval_scores=all_scores,
                num_chunks_retrieved=total_chunks,
                num_chunks_cited=len(cited_chunks),
                num_pages_cited=len(validation.cited_pages),
                num_documents=len(retrieval.doc_names),
                citation_valid=True,
                required_regeneration=required_regeneration,
            ))
            
            return MultiDocQAResult(
                answer=validation.answer,
                sources=cited_chunks,
                cited_pages=validation.cited_pages,
                confidence=confidence,
                success=True,
                required_regeneration=required_regeneration,
            )
        
        logger.warning(f"Validation failed: {validation.error}")
        required_regeneration = True
        
        # Add hint for retry - find and update last user message
        if attempt < max_retries:
            hint = f"\n\nPREVIOUS ATTEMPT HAD ERRORS: {validation.error}\nONLY cite pages from: {sorted(valid_pages)}"
            new_messages = [msg.copy() for msg in messages]
            for i in range(len(new_messages) - 1, -1, -1):
                if new_messages[i]["role"] == "user":
                    new_messages[i]["content"] += hint
                    break
            messages = new_messages
    
    # All retries failed
    return MultiDocQAResult(
        answer="",
        sources=[],
        cited_pages=[],
        confidence=0.0,
        success=False,
        error="Failed to generate valid answer after retries",
        required_regeneration=True,
    )
