"""Gemini API client for LLM generation."""

import asyncio
import hashlib
import logging
from typing import Optional

import google.generativeai as genai

from core.config import settings

logger = logging.getLogger(__name__)

# One-time configuration
_configured = False
# Cache models by system_instruction hash
_model_cache: dict[str, genai.GenerativeModel] = {}


def _ensure_configured():
    """Configure Gemini API once."""
    global _configured
    if _configured:
        return
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    genai.configure(api_key=settings.gemini_api_key)
    _configured = True


def _get_model(system_instruction: str | None = None) -> genai.GenerativeModel:
    """Get or create cached model, optionally with system instruction."""
    _ensure_configured()
    
    # Create cache key from system instruction
    cache_key = hashlib.md5((system_instruction or "").encode()).hexdigest()
    
    if cache_key not in _model_cache:
        if system_instruction:
            _model_cache[cache_key] = genai.GenerativeModel(
                settings.gemini_model,
                system_instruction=system_instruction,
            )
        else:
            _model_cache[cache_key] = genai.GenerativeModel(settings.gemini_model)
        logger.debug(f"Created model with cache key {cache_key[:8]}")
    
    return _model_cache[cache_key]


def _generate_sync(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> str:
    """Synchronous generation call."""
    # Extract system prompt and user content
    system_prompt = None
    user_content = []
    
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            user_content.append(msg["content"])
    
    model = _get_model(system_prompt)
    
    gen_config = genai.GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    
    response = model.generate_content(
        "\n\n".join(user_content),
        generation_config=gen_config,
    )
    
    # Safely access response.text (can raise ValueError if blocked)
    try:
        text = response.text
    except (ValueError, Exception) as e:
        logger.warning(f"Gemini response text access failed: {e}")
        text = None
    
    return text.strip() if text else ""


async def generate_with_gemini(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 1500,
) -> tuple[str, bool, Optional[str]]:
    """
    Generate response using Gemini API.
    
    Returns:
        Tuple of (response_text, success, error_message)
    """
    try:
        result = await asyncio.to_thread(
            _generate_sync, messages, temperature, max_tokens
        )
        
        if result:
            logger.info(f"Gemini generated {len(result)} chars")
            return result, True, None
        
        return "", False, "Empty response from Gemini"
        
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        return "", False, str(e)


async def check_gemini_health() -> bool:
    """Check if Gemini API is accessible."""
    try:
        def _health_check():
            _ensure_configured()
            model = _get_model()
            response = model.generate_content(
                "Say 'ok'",
                generation_config=genai.GenerationConfig(max_output_tokens=10),
            )
            return bool(response.text)
        
        return await asyncio.to_thread(_health_check)
    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        return False
