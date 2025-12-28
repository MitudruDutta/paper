"""Question-answering engine with RAG pipeline."""

import logging
from dataclasses import dataclass

from services.prompt_builder import ChunkContext, build_messages
from services.citation_validator import validate_and_fix_citations
from services.llm_client import generate_answer as llm_generate

logger = logging.getLogger(__name__)

# Generation parameters
MAX_TOKENS = 800
TEMPERATURE = 0.1
MAX_RETRIES = 2


@dataclass
class QAResult:
    """Final QA result with validation."""
    answer: str
    sources: list[ChunkContext]
    cited_pages: list[int]
    success: bool
    error: str | None = None


async def answer_question(
    question: str,
    chunks: list[ChunkContext],
) -> QAResult:
    """
    Generate and validate an answer for the question.
    
    Uses the configured LLM provider (Gemini or Ollama).
    """
    if not chunks:
        logger.warning("No chunks provided for QA")
        return QAResult(
            answer="I cannot find this information in the provided document.",
            sources=[],
            cited_pages=[],
            success=True,
        )
    
    messages, valid_pages = build_messages(chunks, question)
    logger.info(f"Valid pages for citation: {valid_pages}")
    
    last_error = None
    
    for attempt in range(MAX_RETRIES + 1):
        logger.info(f"Generation attempt {attempt + 1}/{MAX_RETRIES + 1}")
        
        # Use LLM router
        answer_text, model_used, success, error = await llm_generate(
            messages, TEMPERATURE, MAX_TOKENS
        )
        
        if not success:
            last_error = error
            logger.error(f"Generation failed ({model_used}): {error}")
            continue
        
        logger.info(f"Generated with {model_used}: {len(answer_text)} chars")
        
        # Validate and fix citations
        validation = validate_and_fix_citations(answer_text, chunks)
        
        if validation.valid:
            logger.info(f"Answer validated. Cited pages: {validation.cited_pages}")
            
            # Filter sources to only chunks that contain cited pages
            cited_sources = []
            if validation.cited_pages:
                cited_pages_set = set(validation.cited_pages)
                for chunk in chunks:
                    chunk_pages = set(range(chunk.page_start, chunk.page_end + 1))
                    if chunk_pages & cited_pages_set:
                        cited_in_chunk = sorted(chunk_pages & cited_pages_set)
                        cited_sources.append(ChunkContext(
                            chunk_id=chunk.chunk_id,
                            document_id=chunk.document_id,
                            content=chunk.content,
                            page_start=cited_in_chunk[0],
                            page_end=cited_in_chunk[-1],
                        ))
            
            return QAResult(
                answer=validation.answer,
                sources=cited_sources,
                cited_pages=validation.cited_pages,
                success=True,
            )
        
        logger.warning(f"Validation failed: {validation.error}")
        last_error = validation.error
        
        # Add hint for retry
        if attempt < MAX_RETRIES:
            hint = f"\n\nPREVIOUS ATTEMPT HAD ERRORS: {validation.error}\nRemember: ONLY cite pages from this list: {valid_pages}"
            messages = [
                messages[0],
                {"role": messages[-1]["role"], "content": messages[-1]["content"] + hint},
            ]
    
    logger.error(f"All retries exhausted. Last error: {last_error}")
    
    return QAResult(
        answer="",
        sources=[],
        cited_pages=[],
        success=False,
        error=f"Failed to generate valid answer: {last_error}",
    )
