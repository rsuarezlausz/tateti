from app.config import Settings
from app.llm.base import LLMClient
from app.llm.mock import MockLLMClient
from app.llm.openrouter import OpenRouterClient


def build_llm_client(settings: Settings) -> LLMClient:
    """Mock si LLM_MOCK=true; si no, OpenRouter (exige key y modelo)."""
    if settings.llm_mock:
        return MockLLMClient()
    return OpenRouterClient(
        settings.openrouter_api_key, settings.openrouter_model, settings.openrouter_base_url
    )
