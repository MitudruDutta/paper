"""LLM client - Gemini API."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def generate_answer(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 1500,
) -> tuple[str, str, bool, Optional[str]]:
    """
    Generate answer using Gemini.
    
    Returns:
        Tuple of (response_text, model_used, success, error_message)
    """
    from services.gemini_client import generate_with_gemini
    from core.config import settings
    
    text, success, error = await generate_with_gemini(
        messages, temperature, max_tokens
    )
    return text, settings.gemini_model, success, error


async def check_llm_health() -> bool:
    """Check if Gemini is healthy."""
    from services.gemini_client import check_gemini_health
    return await check_gemini_health()
