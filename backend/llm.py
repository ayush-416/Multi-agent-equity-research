"""
LLM provider with fallback support.

Supports multiple providers (Gemini, Groq) with automatic fallback
when the primary provider fails or rate limits.
"""
import os
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# Singleton LLM instance
_llm_instance: Optional[BaseChatModel] = None


def get_llm(temperature: float = 0) -> BaseChatModel:
    """
    Get LLM with fallback support.

    Builds primary model from LLM_PROVIDER/LLM_MODEL and fallback from
    LLM_FALLBACK_PROVIDER/LLM_FALLBACK_MODEL (if configured).

    Supported providers:
    - gemini: ChatGoogleGenerativeAI (requires GOOGLE_API_KEY)
    - groq: ChatGroq (requires GROQ_API_KEY)

    Args:
        temperature: Temperature for LLM (0-1)

    Returns:
        BaseChatModel with fallback configured

    Raises:
        ValueError: If provider not supported or API keys missing
    """
    global _llm_instance

    # Return cached instance if temperature matches
    # (Note: In production, you may want to cache per temperature)
    if _llm_instance is not None and temperature == 0:
        return _llm_instance

    # Get primary provider config
    primary_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    primary_model = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    # Build primary LLM
    primary_llm = _build_llm(primary_provider, primary_model, temperature)

    # Get fallback provider config (optional)
    fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER", "").lower()
    fallback_model = os.getenv("LLM_FALLBACK_MODEL", "")

    if fallback_provider and fallback_model:
        try:
            fallback_llm = _build_llm(fallback_provider, fallback_model, temperature)
            logger.info(f"Configured LLM fallback: {primary_provider}/{primary_model} -> {fallback_provider}/{fallback_model}")

            # Use with_fallbacks to chain primary and fallback
            llm = primary_llm.with_fallbacks([fallback_llm])
        except Exception as e:
            logger.warning(f"Failed to configure fallback LLM: {e}, using primary only")
            llm = primary_llm
    else:
        logger.info(f"Using single LLM provider: {primary_provider}/{primary_model}")
        llm = primary_llm

    # Cache if temperature is 0 (default)
    if temperature == 0:
        _llm_instance = llm

    return llm


def _build_llm(provider: str, model: str, temperature: float) -> BaseChatModel:
    """
    Build LLM instance for a specific provider.

    Args:
        provider: "gemini" or "groq"
        model: Model name
        temperature: Temperature (0-1)

    Returns:
        BaseChatModel instance

    Raises:
        ValueError: If provider not supported or API key missing
    """
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key,
            max_retries=0  # Disable retries, let fallback handle failures
        )

    elif provider == "groq":
        from langchain_groq import ChatGroq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")

        return ChatGroq(
            model=model,
            temperature=temperature,
            groq_api_key=api_key,
            max_retries=0  # Disable retries, let fallback handle failures
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported: gemini, groq")


def reset_llm_cache():
    """Reset cached LLM instance (useful for testing)."""
    global _llm_instance
    _llm_instance = None
