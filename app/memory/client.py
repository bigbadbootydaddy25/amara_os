"""Supabase client factory, isolated so callers can inject a fake client in tests."""

from __future__ import annotations

from supabase import Client, create_client

from app.config import Settings


def get_supabase_client(settings: Settings) -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set (see .env.example)"
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
