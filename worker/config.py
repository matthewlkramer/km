"""Configuration utilities for the Cloud Run worker."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional


@dataclass
class Config:
    """Runtime configuration derived from environment variables."""

    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: Optional[str]
    openai_api_key: Optional[str]
    drive_service_account: Dict[str, Any]
    root_drive_id: str
    manual_trigger_token: Optional[str]

    @property
    def has_embeddings(self) -> bool:
        return bool(self.openai_api_key)


def _load_service_account() -> Dict[str, Any]:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT env var is required")

    if raw.strip().startswith("{"):
        return json.loads(raw)

    # Assume base64 encoded json string
    try:
        decoded = base64.b64decode(raw)
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError("Invalid GOOGLE_SERVICE_ACCOUNT payload") from exc
    return json.loads(decoded)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the singleton configuration for the worker."""

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_service_key:
        raise RuntimeError("Supabase URL and service role key must be configured")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")

    root_drive_id = os.getenv("KM_ROOT_DRIVE_ID", "")
    if not root_drive_id:
        raise RuntimeError("KM_ROOT_DRIVE_ID must be configured")

    manual_trigger_token = os.getenv("MANUAL_TRIGGER_TOKEN")

    return Config(
        supabase_url=supabase_url,
        supabase_service_key=supabase_service_key,
        supabase_anon_key=supabase_anon_key,
        openai_api_key=openai_api_key,
        drive_service_account=_load_service_account(),
        root_drive_id=root_drive_id,
        manual_trigger_token=manual_trigger_token,
    )


__all__ = ["Config", "get_config"]
