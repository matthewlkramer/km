"""Utilities for text extraction, chunking, and embedding."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Sequence

import httpx

from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    file_id: str
    chunk_index: int
    content: str
    tokens: int | None
    embedding: List[float] | None

    def as_payload(self) -> dict:
        return {
            "file_id": self.file_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "tokens": self.tokens,
            "embedding": self.embedding,
        }


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def chunk_text(text: str, file_id: str, max_tokens: int = 800, overlap: int = 200) -> List[Chunk]:
    """Simple token-aware chunking based on paragraph boundaries."""
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: List[Chunk] = []
    current: List[str] = []
    token_count = 0
    chunk_index = 0

    for paragraph in paragraphs:
        tokens = len(paragraph.split())
        if token_count + tokens > max_tokens and current:
            content = "\n\n".join(current)
            chunks.append(Chunk(file_id, chunk_index, content, token_count, None))
            chunk_index += 1
            if overlap > 0:
                overlap_tokens = 0
                overlap_paragraphs: List[str] = []
                for prev in reversed(current):
                    overlap_paragraphs.insert(0, prev)
                    overlap_tokens += len(prev.split())
                    if overlap_tokens >= overlap:
                        break
                current = overlap_paragraphs.copy()
                token_count = overlap_tokens
            else:
                current = []
                token_count = 0

        current.append(paragraph)
        token_count += tokens

    if current:
        content = "\n\n".join(current)
        chunks.append(Chunk(file_id, chunk_index, content, token_count, None))

    return chunks


def embed_chunks(chunks: Sequence[Chunk]) -> Sequence[Chunk]:
    cfg = get_config()
    if not cfg.has_embeddings:
        logger.warning("OPENAI_API_KEY not configured; skipping embedding generation")
        return chunks

    client = httpx.Client(
        base_url="https://api.openai.com/v1",
        headers={
            "Authorization": f"Bearer {cfg.openai_api_key}",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )
    try:
        for chunk in chunks:
            response = client.post(
                "/embeddings",
                json={
                    "model": "text-embedding-3-large",
                    "input": chunk.content,
                },
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("data", [{}])[0].get("embedding")
            chunk.embedding = embedding
            chunk.tokens = data.get("usage", {}).get("total_tokens", chunk.tokens)
    finally:
        client.close()

    return chunks


__all__ = ["Chunk", "chunk_text", "embed_chunks"]
