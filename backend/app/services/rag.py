from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.core.errors import (
    BookNotFoundError,
    DocumentTooLargeError,
    GenerationError,
    InvalidDocumentError,
    InvalidQuestionError,
    ModelUnavailableError,
)
from app.domain.documents import (
    BookSummary,
    GeneratedAnswer,
    RagStreamEvent,
    RetrievedChunk,
)
from app.infrastructure.chroma_store import ChromaBookIndex
from app.services.answerer import Answerer, ExtractiveAnswerer, build_answerer
from app.services.document_loader import decode_document, validate_document_name
from app.services.embedding import Embedder, SentenceTransformerEmbedder
from app.services.reranker import (
    CrossEncoderReranker,
    PassThroughReranker,
    Reranker,
)
from app.services.text_splitter import TextSplitter

logger = logging.getLogger(__name__)


class RagService:
    def __init__(
        self,
        settings: Settings,
        *,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        answerer: Answerer | None = None,
        index: ChromaBookIndex | None = None,
        splitter: TextSplitter | None = None,
    ) -> None:
        self.settings = settings
        self.embedder = embedder or SentenceTransformerEmbedder(settings)
        if reranker is not None:
            self.reranker = reranker
        elif settings.reranker_enabled:
            self.reranker = CrossEncoderReranker(settings)
        else:
            self.reranker = PassThroughReranker()
        self.answerer = answerer or build_answerer(settings)
        self.fallback_answerer = ExtractiveAnswerer()
        self.index = index or ChromaBookIndex(
            settings.chroma_dir,
            batch_size=settings.ingestion_batch_size,
        )
        self.splitter = splitter or TextSplitter(
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )

    def create_book(self, file_name: str, raw: bytes, title: str | None = None) -> BookSummary:
        source_name = validate_document_name(file_name)
        if len(raw) > self.settings.upload_max_bytes:
            limit_mb = self.settings.upload_max_bytes / 1024 / 1024
            raise DocumentTooLargeError(f"文档超过 {limit_mb:.0f} MB 限制")

        text, _encoding = decode_document(raw)
        chunks = self.splitter.split(text)
        if not chunks:
            raise InvalidDocumentError("文档切块后没有可索引内容")
        if len(chunks) > self.settings.max_chunks_per_book:
            raise DocumentTooLargeError(
                f"文档切块数量超过 {self.settings.max_chunks_per_book} 个限制"
            )

        book_id = uuid.uuid4().hex
        clean_title = (title or Path(source_name).stem).strip() or Path(source_name).stem
        book = BookSummary(
            id=book_id,
            title=clean_title[:200],
            source_name=source_name,
            character_count=len(text),
            chunk_count=len(chunks),
            created_at=datetime.now(UTC).isoformat(),
            content_sha256=hashlib.sha256(raw).hexdigest(),
        )
        book_dir = self.settings.books_dir / book_id
        book_dir.mkdir(parents=True, exist_ok=True)
        source_path = book_dir / f"source{Path(source_name).suffix.lower()}"
        source_path.write_bytes(raw)

        try:
            embeddings = self.embedder.embed_documents([chunk.text for chunk in chunks])
            if len(embeddings) != len(chunks):
                raise ModelUnavailableError("向量数量与文本片段数量不一致")
            self.index.add_book(book, chunks, embeddings)
        except Exception:
            self.index.delete_book(book_id)
            shutil.rmtree(book_dir, ignore_errors=True)
            raise

        return book

    def list_books(self) -> list[BookSummary]:
        return self.index.list_books()

    def get_book(self, book_id: str) -> BookSummary:
        book = self.index.get_book(book_id)
        if book is None:
            raise BookNotFoundError(f"未找到书籍：{book_id}")
        return book

    def delete_book(self, book_id: str) -> None:
        if not self.index.delete_book(book_id):
            raise BookNotFoundError(f"未找到书籍：{book_id}")
        shutil.rmtree(self.settings.books_dir / book_id, ignore_errors=True)

    def ask(
        self, question: str, book_id: str | None = None, top_k: int = 3
    ) -> tuple[
        list[RetrievedChunk],
        GeneratedAnswer,
    ]:
        clean_question, evidence = self._prepare_evidence(question, book_id, top_k)
        if not evidence:
            return [], self.fallback_answerer.answer(clean_question, [])

        try:
            answer = self.answerer.answer(clean_question, evidence)
        except (GenerationError, ModelUnavailableError) as exc:
            logger.warning("生成模型不可用，降级为检索摘录：%s", exc)
            answer = self.fallback_answerer.answer(clean_question, evidence)
        return evidence, answer

    def stream_answer(
        self,
        question: str,
        book_id: str | None = None,
        top_k: int = 3,
    ) -> Iterator[RagStreamEvent]:
        clean_question, evidence = self._prepare_evidence(question, book_id, top_k)
        yield RagStreamEvent(
            event="meta",
            data={
                "question": clean_question,
                "evidence": evidence,
            },
        )

        if not evidence:
            yield from self._stream_fallback(clean_question, evidence)
            return

        mode = "extractive"
        model: str | None = None
        emitted = False
        try:
            for delta in self.answerer.stream(clean_question, evidence):
                emitted = True
                mode = delta.mode
                model = delta.model
                yield RagStreamEvent(
                    event="delta",
                    data={
                        "text": delta.text,
                        "mode": delta.mode,
                        "model": delta.model,
                    },
                )
        except (GenerationError, ModelUnavailableError) as exc:
            logger.warning("流式生成中断：%s", exc)
            if emitted:
                yield RagStreamEvent(
                    event="error",
                    data={
                        "code": "stream_interrupted",
                        "message": "回答生成中断，请重试",
                    },
                )
            else:
                yield from self._stream_fallback(clean_question, evidence)
            return

        yield RagStreamEvent(
            event="done",
            data={
                "mode": mode,
                "model": model,
            },
        )

    def _prepare_evidence(
        self,
        question: str,
        book_id: str | None,
        top_k: int,
    ) -> tuple[str, list[RetrievedChunk]]:
        clean_question = question.strip()
        if not clean_question:
            raise InvalidQuestionError("问题不能为空")
        book_id = book_id.strip() if book_id else None
        if book_id is not None:
            self.get_book(book_id)
        elif not self.index.list_books():
            return clean_question, []

        query_embedding = self.embedder.embed_query(clean_question)
        candidates = self.index.retrieve(
            query_embedding,
            top_k=max(self.settings.retrieval_candidates, top_k),
            book_id=book_id,
        )
        if not candidates:
            return clean_question, []

        try:
            evidence = self.reranker.rank(clean_question, candidates, top_k)
        except ModelUnavailableError as exc:
            logger.warning("重排模型不可用，降级为向量召回顺序：%s", exc)
            evidence = candidates[:top_k]
        return clean_question, evidence

    def _stream_fallback(
        self,
        question: str,
        evidence: list[RetrievedChunk],
    ) -> Iterator[RagStreamEvent]:
        mode = "extractive"
        for delta in self.fallback_answerer.stream(question, evidence):
            mode = delta.mode
            yield RagStreamEvent(
                event="delta",
                data={
                    "text": delta.text,
                    "mode": delta.mode,
                    "model": None,
                },
            )
        yield RagStreamEvent(
            event="done",
            data={
                "mode": mode,
                "model": None,
            },
        )
