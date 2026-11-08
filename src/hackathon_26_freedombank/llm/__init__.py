from .. import config
from .base import LLMClient, LLMError

PROVIDERS = ("gemini", "ollama")


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Build the LLM client for `provider` (defaults to LLM_PROVIDER from .env)."""
    provider = (provider or config.LLM_PROVIDER).lower()
    if provider == "gemini":
        from .gemini import GeminiClient

        return GeminiClient(config.GEMINI_API_KEY, config.GEMINI_MODEL)
    if provider == "ollama":
        from .ollama import OllamaClient

        return OllamaClient(
            config.OLLAMA_HOST,
            config.OLLAMA_MODEL,
            think=config.OLLAMA_THINK,
            num_ctx=config.OLLAMA_NUM_CTX,
            num_predict=config.OLLAMA_NUM_PREDICT,
            temperature=config.OLLAMA_TEMPERATURE,
            timeout=config.OLLAMA_TIMEOUT,
        )
    raise LLMError(f"Unknown LLM provider {provider!r}; expected one of {PROVIDERS}")


__all__ = ["PROVIDERS", "LLMClient", "LLMError", "get_llm_client"]
