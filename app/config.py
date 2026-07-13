"""Env + YAML configuration loader for AMARA OS.

Secrets come from the environment (.env, loaded via python-dotenv).
Everything else -- workspace registry, client registry, routing table,
identity/visual constants, Phase 2 presence stubs -- comes from config.yaml.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"

Workspace = Literal["texhoma", "acesn8s_dev", "personal_investments"]

load_dotenv(REPO_ROOT / ".env")


class ClientConfig(BaseModel):
    id: str
    name: str
    workspace: Workspace
    active: bool = True


class RouteConfig(BaseModel):
    provider: Literal["ollama", "anthropic"]
    model: str | None = None


class OllamaConfig(BaseModel):
    base_url_env: str = "OLLAMA_BASE_URL"
    default_base_url: str = "http://localhost:11434"
    default_model: str = "llama3.1"
    embedding_model: str = "nomic-embed-text"

    @property
    def base_url(self) -> str:
        return os.environ.get(self.base_url_env) or self.default_base_url


class AnthropicConfig(BaseModel):
    api_key_env: str = "ANTHROPIC_API_KEY"
    default_model: str = "claude-sonnet-4-5"

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) or None


class ProvidersConfig(BaseModel):
    ollama: OllamaConfig
    anthropic: AnthropicConfig


class LLMConfig(BaseModel):
    providers: ProvidersConfig
    routing: dict[str, RouteConfig]

    def route_for(self, task_type: str) -> RouteConfig:
        return self.routing.get(task_type, self.routing["default"])


class GuardsConfig(BaseModel):
    blacklist_terms: list[str]
    ai_names: list[str]


class AvatarConfig(BaseModel):
    material: str
    eyes: str
    halo: str


class VisualConfig(BaseModel):
    background_color: str
    accent_color: str
    typography: str
    avatar: AvatarConfig


class IdentityConfig(BaseModel):
    name: str
    branding_line: str
    visual: VisualConfig


class PresenceConfig(BaseModel):
    elevenlabs_voice_id: str = ""
    heygen_avatar_id: str = ""
    heygen_mode: str = "lite"


class AppMeta(BaseModel):
    name: str
    phase: int


class Settings(BaseModel):
    app: AppMeta
    workspaces: list[Workspace]
    clients: list[ClientConfig]
    llm: LLMConfig
    guards: GuardsConfig
    identity: IdentityConfig
    presence: PresenceConfig

    @property
    def supabase_url(self) -> str | None:
        return os.environ.get("SUPABASE_URL") or None

    @property
    def supabase_service_role_key(self) -> str | None:
        return os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or None


@lru_cache
def get_settings() -> Settings:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Settings.model_validate(raw)
