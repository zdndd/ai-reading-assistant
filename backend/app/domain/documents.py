from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    book_id: str
    book_title: str
    chunk_index: int
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: IndexedChunk
    retrieval_score: float
    rerank_score: float | None = None


@dataclass(frozen=True)
class BookSummary:
    id: str
    title: str
    source_name: str
    character_count: int
    chunk_count: int
    created_at: str
    content_sha256: str


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    mode: str
    model: str | None = None


@dataclass(frozen=True)
class AnswerDelta:
    text: str
    mode: str
    model: str | None = None


@dataclass(frozen=True)
class RagStreamEvent:
    event: str
    data: dict[str, Any]
