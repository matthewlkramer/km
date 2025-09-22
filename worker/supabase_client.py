"""Supabase integration helpers."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

import httpx

from .config import get_config

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Thin wrapper over the Supabase REST and RPC endpoints."""

    def __init__(self) -> None:
        cfg = get_config()
        self._client = httpx.Client(
            base_url=f"{cfg.supabase_url}/rest/v1",
            headers={
                "apikey": cfg.supabase_service_key,
                "Authorization": f"Bearer {cfg.supabase_service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            timeout=30.0,
        )
        self._rpc_client = httpx.Client(
            base_url=f"{cfg.supabase_url}/rest/v1",
            headers={
                "apikey": cfg.supabase_service_key,
                "Authorization": f"Bearer {cfg.supabase_service_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._cfg = cfg

    def close(self) -> None:
        self._client.close()
        self._rpc_client.close()

    # --- Files metadata -------------------------------------------------
    def upsert_file_metadata(self, payload: Dict[str, Any]) -> str:
        """Invoke the `upsert_file_metadata` RPC."""
        response = self._rpc_client.post(
            "/rpc/upsert_file_metadata",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, str):
            return data
        raise RuntimeError("Unexpected response from upsert_file_metadata")

    def update_chunks(self, file_id: str, chunks: Iterable[Dict[str, Any]]) -> None:
        """Replace the chunk records for a file."""
        delete_resp = self._client.delete(
            "/chunks",
            params={"file_id": f"eq.{file_id}"},
        )
        delete_resp.raise_for_status()

        payload = list(chunks)
        if not payload:
            return

        insert_resp = self._client.post("/chunks", json=payload)
        insert_resp.raise_for_status()

    def record_drive_page_token(self, token: str) -> None:
        resp = self._rpc_client.post(
            "/rpc/set_drive_start_page_token",
            json={"p_token": token},
        )
        resp.raise_for_status()

    def store_feedback(self, payload: Dict[str, Any]) -> None:
        resp = self._client.post("/feedback", json=payload)
        resp.raise_for_status()

    def fetch_pending_answers(self) -> List[Dict[str, Any]]:
        resp = self._client.get(
            "/answers",
            params={"approved": "eq.false"},
        )
        resp.raise_for_status()
        return resp.json()


__all__ = ["SupabaseClient"]
