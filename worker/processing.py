"""Core processing workflow for Drive sync and indexing."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable, Optional

from dateutil import parser as date_parser

from .drive import DriveClient, DriveFile
from .supabase_client import SupabaseClient
from .text_processing import Chunk, chunk_text, embed_chunks

logger = logging.getLogger(__name__)

SUPPORTED_EXPORTS = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


def _derive_path(stack: Iterable[str]) -> str:
    return ".".join(stack)


def _normalise_timestamp(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return date_parser.isoparse(value).isoformat()
    except (ValueError, TypeError):  # pragma: no cover - defensive
        return None


class Processor:
    def __init__(self, drive_client: DriveClient, supabase: SupabaseClient) -> None:
        self.drive = drive_client
        self.supabase = supabase

    # ------------------------------------------------------------------
    def bootstrap_folder(self, folder_id: Optional[str] = None, path_stack: Optional[list[str]] = None) -> None:
        folder_id = folder_id or self.drive.root_id
        path_stack = path_stack or [folder_id]
        items = self.drive.list_children(folder_id)
        logger.info("Bootstrap found %d items in %s", len(items), folder_id)

        for item in items:
            ltree_path = _derive_path(path_stack + [item.id])
            payload = {
                "p_drive_id": item.id,
                "p_parent_drive_id": (item.parents[0] if item.parents else None),
                "p_path": ltree_path,
                "p_mime_type": item.mime_type,
                "p_title": item.name,
                "p_checksum": item.md5_checksum,
                "p_modified_at": _normalise_timestamp(item.modified_time),
                "p_last_reviewed_at": None,
                "p_core": False,
                "p_audience": [],
                "p_age_levels": [],
                "p_geographies": [],
                "p_governance_models": [],
                "p_vouchers": None,
                "p_created_by": None,
                "p_maintained_by": None,
                "p_raw_export_path": None,
            }
            file_id = self.supabase.upsert_file_metadata(payload)
            logger.info("Upserted metadata for %s (%s)", item.name, file_id)

            if item.mime_type == "application/vnd.google-apps.folder":
                self.bootstrap_folder(item.id, path_stack + [item.id])
            else:
                self._process_file_content(item, file_id)

    # ------------------------------------------------------------------
    def handle_change(self, file_id: str) -> None:
        drive_file = self.drive.get_file(file_id)
        if not drive_file:
            logger.warning("File %s not accessible", file_id)
            return

        if drive_file.mime_type == "application/vnd.google-apps.folder":
            self.bootstrap_folder(file_id)
            return

        ltree_path = _derive_path([drive_file.parents[0], drive_file.id]) if drive_file.parents else drive_file.id
        payload = {
            "p_drive_id": drive_file.id,
            "p_parent_drive_id": (drive_file.parents[0] if drive_file.parents else None),
            "p_path": ltree_path,
            "p_mime_type": drive_file.mime_type,
            "p_title": drive_file.name,
            "p_checksum": drive_file.md5_checksum,
            "p_modified_at": _normalise_timestamp(drive_file.modified_time),
            "p_last_reviewed_at": None,
            "p_core": False,
            "p_audience": [],
            "p_age_levels": [],
            "p_geographies": [],
            "p_governance_models": [],
            "p_vouchers": None,
            "p_created_by": None,
            "p_maintained_by": None,
            "p_raw_export_path": None,
        }
        record_id = self.supabase.upsert_file_metadata(payload)
        self._process_file_content(drive_file, record_id)

    # ------------------------------------------------------------------
    def _process_file_content(self, drive_file: DriveFile, file_id: str) -> None:
        if drive_file.mime_type not in SUPPORTED_EXPORTS:
            logger.info("Skipping unsupported mime type %s", drive_file.mime_type)
            return

        export_type = SUPPORTED_EXPORTS[drive_file.mime_type]
        text_content = self.drive.export_file(drive_file.id, mime_type=export_type)
        chunks = chunk_text(text_content, file_id)
        chunks = list(embed_chunks(chunks))
        payloads = [chunk.as_payload() for chunk in chunks]
        self.supabase.update_chunks(file_id, payloads)
        logger.info("Updated %d chunks for %s", len(payloads), drive_file.name)


__all__ = ["Processor"]
