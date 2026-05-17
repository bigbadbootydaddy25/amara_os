import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # Routing
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
    claude_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Memory
    mem0_api_key: str = os.getenv("MEM0_API_KEY", "")
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    obsidian_vault_path: str = os.getenv("OBSIDIAN_VAULT_PATH", "~/obsidian-vault")

    # Observability
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Miro
    miro_access_token: str = os.getenv("MIRO_ACCESS_TOKEN", "")
    miro_board_id: str = os.getenv("MIRO_BOARD_ID", "")

    # Predictor
    improvement_loop_hour: int = int(os.getenv("IMPROVEMENT_LOOP_HOUR", "3"))

    # Qdrant
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    qdrant_use_https: bool = os.getenv("QDRANT_USE_HTTPS", "false").lower() == "true"

    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))


cfg = Config()
