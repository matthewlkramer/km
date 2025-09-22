"""Google Drive integration helpers."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import List, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .config import get_config

logger = logging.getLogger(__name__)


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    parents: List[str]
    md5_checksum: Optional[str]
    modified_time: str


class DriveClient:
    def __init__(self) -> None:
        cfg = get_config()
        credentials = Credentials.from_service_account_info(
            cfg.drive_service_account,
            scopes=SCOPES,
        )
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._root_id = cfg.root_drive_id

    @property
    def root_id(self) -> str:
        return self._root_id

    def get_file(self, file_id: str) -> Optional[DriveFile]:
        resource = (
            self._service.files()
            .get(fileId=file_id, fields="id, name, mimeType, parents, md5Checksum, modifiedTime")
            .execute()
        )
        if not resource:
            return None
        return DriveFile(
            id=resource["id"],
            name=resource["name"],
            mime_type=resource["mimeType"],
            parents=resource.get("parents", []),
            md5_checksum=resource.get("md5Checksum"),
            modified_time=resource.get("modifiedTime"),
        )

    def list_children(self, folder_id: Optional[str] = None) -> List[DriveFile]:
        folder_id = folder_id or self._root_id
        query = f"'{folder_id}' in parents and trashed = false"
        page_token: Optional[str] = None
        items: List[DriveFile] = []

        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    pageSize=1000,
                    fields="nextPageToken, files(id, name, mimeType, parents, md5Checksum, modifiedTime)",
                    pageToken=page_token,
                )
                .execute()
            )
            for item in response.get("files", []):
                items.append(
                    DriveFile(
                        id=item["id"],
                        name=item["name"],
                        mime_type=item["mimeType"],
                        parents=item.get("parents", []),
                        md5_checksum=item.get("md5Checksum"),
                        modified_time=item.get("modifiedTime"),
                    )
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return items

    def export_file(self, file_id: str, mime_type: str = "text/plain") -> str:
        request = self._service.files().export(fileId=file_id, mimeType=mime_type)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug("Export progress %s%%", int(status.progress() * 100))
        return fh.getvalue().decode("utf-8")

    def download_file(self, file_id: str) -> bytes:
        request = self._service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug("Download progress %s%%", int(status.progress() * 100))
        return fh.getvalue()


__all__ = ["DriveClient", "DriveFile"]
