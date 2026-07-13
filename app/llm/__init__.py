from app.config import Settings
from app.llm.claude_client import ClaudeProvider
from app.llm.ollama_client import OllamaProvider
from app.llm.provider import LLMProvider

__all__ = ["LLMProvider", "OllamaProvider", "ClaudeProvider", "build_providers"]


def build_providers(settings: Settings) -> dict[str, LLMProvider]:
    ollama_cfg = settings.llm.providers.ollama
    anthropic_cfg = settings.llm.providers.anthropic
    return {
        "ollama": OllamaProvider(
            base_url=ollama_cfg.base_url,
            default_model=ollama_cfg.default_model,
            embedding_model=ollama_cfg.embedding_model,
        ),
        "anthropic": ClaudeProvider(
            api_key=anthropic_cfg.api_key,
            default_model=anthropic_cfg.default_model,
        ),
    }
