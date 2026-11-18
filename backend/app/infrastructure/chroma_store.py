from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import chromadb

from app.domain.documents import (
    BookSummary,
    ChunkDraft,
    IndexedChunk,
    RetrievedChunk,
)


class ChromaBookIndex:
    def __init__(
        self,
        path: Path,
        collection_name: str = "reading_chunks",
        batch_size: int = 64,
    ) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._lock = threading.Lock()

    def add_book(
        self,
        book: BookSummary,
        chunks: list[ChunkDraft],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 数量不一致")

        for offset in range(0, len(chunks), self.batch_size):
            batch_chunks = chunks[offset : offset + self.batch_size]
            batch_embeddings = embeddings[offset : offset + self.batch_size]
            ids = [f"{book.id}:{offset + index:05d}" for index in range(len(batch_chunks))]
            metadatas = [
                {
                    "book_id": book.id,
                    "book_title": book.title,
                    "source_name": book.source_name,
                    "character_count": book.character_count,
                    "chunk_count": book.chunk_count,
                    "created_at": book.created_at,
                    "content_sha256": book.content_sha256,
                    "chunk_index": offset + index,
                    "char_start": chunk.start,
                    "char_end": chunk.end,
                }
                for index, chunk in enumerate(batch_chunks)
            ]
            documents = [chunk.text for chunk in batch_chunks]
            with self._lock:
                self._collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=batch_embeddings,
                )

    def list_books(self) -> list[BookSummary]:
        result = self._collection.get(include=["metadatas"])
        grouped: dict[str, list[dict[str, Any]]] = {}
        for metadata in result.get("metadatas") or []:
            if not metadata:
                continue
            book_id = str(metadata.get("book_id", ""))
            if book_id:
                grouped.setdefault(book_id, []).append(dict(metadata))

        books = [self._metadata_to_summary(items[0], len(items)) for items in grouped.values()]
        books.sort(key=lambda item: item.created_at, reverse=True)
        return books

    def get_book(self, book_id: str) -> BookSummary | None:
        result = self._collection.get(
            where={"book_id": book_id},
            include=["metadatas"],
        )
        metadatas = result.get("metadatas") or []
        if not metadatas or not metadatas[0]:
            return None
        return self._metadata_to_summary(dict(metadatas[0]), len(metadatas))

    def delete_book(self, book_id: str) -> bool:
        if self.get_book(book_id) is None:
            return False
        with self._lock:
            self._collection.delete(where={"book_id": book_id})
        return True

    def retrieve(
        self,
        query_embedding: list[float],
        top_k: int,
        book_id: str | None = None,
    ) -> list[RetrievedChunk]:
        where = {"book_id": book_id} if book_id else None
        matching_ids = self._collection.get(where=where, include=[])
        match_count = len(matching_ids.get("ids") or [])
        if match_count == 0:
            return []

        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, match_count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        retrieved: list[RetrievedChunk] = []
        for chunk_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=True,
        ):
            if not document or not metadata:
                continue
            chunk = IndexedChunk(
                chunk_id=chunk_id,
                book_id=str(metadata.get("book_id", "")),
                book_title=str(metadata.get("book_title", "")),
                chunk_index=int(metadata.get("chunk_index", 0)),
                text=document,
            )
            retrieved.append(
                RetrievedChunk(
                    chunk=chunk,
                    retrieval_score=max(-1.0, 1.0 - float(distance)),
                )
            )
        return retrieved

    @staticmethod
    def _metadata_to_summary(metadata: dict[str, Any], chunk_count: int) -> BookSummary:
        return BookSummary(
            id=str(metadata.get("book_id", "")),
            title=str(metadata.get("book_title", "")),
            source_name=str(metadata.get("source_name", "")),
            character_count=int(metadata.get("character_count", 0)),
            chunk_count=int(metadata.get("chunk_count", chunk_count)),
            created_at=str(metadata.get("created_at", "")),
            content_sha256=str(metadata.get("content_sha256", "")),
        )
