"""FastAPI application entrypoint for the Cloud Run worker."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Request

from .config import get_config
from .drive import DriveClient
from .processing import Processor
from .supabase_client import SupabaseClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="KM Drive Worker", version="0.1.0")


@asynccontextmanager
async def processor_context() -> Processor:
    drive = DriveClient()
    supabase = SupabaseClient()
    processor = Processor(drive, supabase)
    try:
        yield processor
    finally:
        supabase.close()


@app.get("/health")
async def healthcheck() -> Dict[str, Any]:
    cfg = get_config()
    return {"status": "ok", "has_embeddings": cfg.has_embeddings}


@app.post("/drive/webhook")
async def drive_webhook(
    request: Request,
    x_goog_resource_id: str = Header(default=""),
    x_km_start_page_token: str | None = Header(default=None),
) -> Dict[str, Any]:
    body = await request.json()
    logger.info("Received Drive webhook %s", body)
    changes = body.get("changes", [])

    processed: list[str] = []
    async with processor_context() as processor:
        for change in changes:
            file_id = change.get("fileId") or change.get("id")
            if not file_id:
                continue
            processor.handle_change(file_id)
            processed.append(file_id)

        if x_km_start_page_token:
            processor.supabase.record_drive_page_token(x_km_start_page_token)

    return {"processed": processed, "resource_id": x_goog_resource_id}


@app.post("/reindex/{drive_id}")
async def manual_reindex(drive_id: str, request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    cfg = get_config()
    if cfg.manual_trigger_token and authorization != f"Bearer {cfg.manual_trigger_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with processor_context() as processor:
        processor.handle_change(drive_id)
    return {"status": "scheduled", "drive_id": drive_id}


@app.post("/bootstrap")
async def bootstrap(request: Request, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    cfg = get_config()
    if cfg.manual_trigger_token and authorization != f"Bearer {cfg.manual_trigger_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    async with processor_context() as processor:
        processor.bootstrap_folder()
    return {"status": "completed"}


__all__ = ["app"]
