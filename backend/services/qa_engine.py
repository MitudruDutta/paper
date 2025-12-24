"""Question-answering engine with RAG pipeline."""

import logging
import os
import uuid
from dataclasses import dataclass

import httpx

from services.prompt_builder import ChunkContext, build_messages
from services.citation_validator import validate_and_fix_citations

logger = logging.getLogger(__name__)

# LLM Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "172.17.0.1")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434"
LOCAL_MODEL = os.getenv("QA_LOCAL_MODEL", "llama3.1:8b")
FALLBACK_MODEL = os.getenv("QA_FALLBACK_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Generation parameters
MAX_TOKENS = 800
TEMPERATURE = 0.1  # Lower for more deterministic
MAX_RETRIES = 2  # Increased retries


@dataclass
class GenerationResult:
    """Result of LLM generation."""
    answer: str
    model_used: str
    success: bool
    error: str | None = None


@dataclass
class QAResult:
    """Final QA result with validation."""
    answer: str
    sources: list[ChunkContext]
    cited_pages: list[int]
    success: bool
    error: str | None = None


async def check_ollama_health(http_client: httpx.AsyncClient) -> bool:
    """Check if Ollama is reachable and model is loaded."""
    try:
        response = await http_client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            if LOCAL_MODEL in models or LOCAL_MODEL.split(":")[0] in [m.split(":")[0] for m in models]:
                return True
            logger.warning(f"Model {LOCAL_MODEL} not found in Ollama. Available: {models}")
        return False
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        return False


async def generate_with_ollama(
    messages: list[dict],
    http_client: httpx.AsyncClient,
) -> GenerationResult:
    """Generate answer using local Ollama model."""
    try:
        response = await http_client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LOCAL_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": TEMPERATURE,
                    "num_predict": MAX_TOKENS,
                },
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        answer = data["message"]["content"].strip()
        
        logger.info(f"Generated answer with {LOCAL_MODEL} ({len(answer)} chars)")
        return GenerationResult(answer=answer, model_used=LOCAL_MODEL, success=True)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama HTTP error: {e.response.status_code}")
        return GenerationResult(answer="", model_used=LOCAL_MODEL, success=False, error=f"HTTP {e.response.status_code}")
    except httpx.ConnectError as e:
        logger.error(f"Ollama connection error: {e}")
        return GenerationResult(answer="", model_used=LOCAL_MODEL, success=False, error="Connection failed - is Ollama running?")
    except httpx.TimeoutException:
        logger.error("Ollama request timed out")
        return GenerationResult(answer="", model_used=LOCAL_MODEL, success=False, error="Request timed out")
    except (KeyError, ValueError) as e:
        logger.error(f"Ollama response parse error: {e}")
        return GenerationResult(answer="", model_used=LOCAL_MODEL, success=False, error=str(e))


async def generate_with_openai(
    messages: list[dict],
    http_client: httpx.AsyncClient,
) -> GenerationResult:
    """Generate answer using OpenAI fallback model."""
    if not OPENAI_API_KEY:
        return GenerationResult(
            answer="",
            model_used=FALLBACK_MODEL,
            success=False,
            error="OpenAI API key not configured",
        )
    
    try:
        response = await http_client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": FALLBACK_MODEL,
                "messages": messages,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
        
        logger.info(f"Generated answer with {FALLBACK_MODEL} (fallback)")
        return GenerationResult(answer=answer, model_used=FALLBACK_MODEL, success=True)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI HTTP error: {e.response.status_code}")
        return GenerationResult(answer="", model_used=FALLBACK_MODEL, success=False, error=str(e))
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return GenerationResult(answer="", model_used=FALLBACK_MODEL, success=False, error=str(e))


async def generate_answer(
    messages: list[dict],
    http_client: httpx.AsyncClient,
) -> GenerationResult:
    """Generate answer, falling back to OpenAI if local fails."""
    # Check Ollama health first
    if await check_ollama_health(http_client):
        result = await generate_with_ollama(messages, http_client)
        if result.success:
            return result
        logger.warning(f"Local model failed: {result.error}")
    else:
        logger.warning("Ollama not available, trying fallback")
    
    # Try fallback
    return await generate_with_openai(messages, http_client)


async def answer_question(
    question: str,
    chunks: list[ChunkContext],
    http_client: httpx.AsyncClient,
) -> QAResult:
    """
    Generate and validate an answer for the question.
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
        
        gen_result = await generate_answer(messages, http_client)
        
        if not gen_result.success:
            last_error = gen_result.error
            logger.error(f"Generation failed: {gen_result.error}")
            continue
        
        answer = gen_result.answer
        logger.debug(f"Raw answer: {answer[:200]}...")
        
        # Validate and fix citations
        validation = validate_and_fix_citations(answer, chunks)
        
        if validation.valid:
            logger.info(f"Answer validated. Cited pages: {validation.cited_pages}")
            
            # Filter sources to only chunks that contain cited pages.
            # NOTE: We narrow page_start/page_end to cited pages only, but keep the full
            # chunk.content unchanged. This is intentional - the content may span more pages
            # than the narrowed range, but we preserve it for context. The page range in the
            # response indicates which pages were actually cited, not the full content span.
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
                            content=chunk.content,  # Full content preserved intentionally
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
        
        # Add hint to messages for retry (create new list to avoid mutating original)
        if attempt < MAX_RETRIES:
            hint = f"\n\nPREVIOUS ATTEMPT HAD ERRORS: {validation.error}\nRemember: ONLY cite pages from this list: {valid_pages}"
            messages = [
                messages[0],
                {"role": messages[-1]["role"], "content": messages[-1]["content"] + hint},
            ]
    
    # All retries exhausted - return best effort if we have something
    logger.error(f"All retries exhausted. Last error: {last_error}")
    
    return QAResult(
        answer="",
        sources=[],
        cited_pages=[],
        success=False,
        error=f"Failed to generate valid answer: {last_error}",
    )
