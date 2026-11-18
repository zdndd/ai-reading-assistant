from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rag_service
from app.core.config import Settings
from app.domain.documents import AnswerDelta, GeneratedAnswer, RetrievedChunk
from app.main import create_app
from app.services.rag import RagService


class FakeEmbedder:
    dimensions = 64

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:2], "big") % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class FakeReranker:
    def rank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        query_terms = set(query)
        reranked = [
            RetrievedChunk(
                chunk=item.chunk,
                retrieval_score=item.retrieval_score,
                rerank_score=float(len(query_terms & set(item.chunk.text))),
            )
            for item in candidates
        ]
        reranked.sort(key=lambda item: item.rerank_score or 0, reverse=True)
        return reranked[:top_k]


class FakeAnswerer:
    def answer(self, question: str, evidence: list[RetrievedChunk]) -> GeneratedAnswer:
        return GeneratedAnswer(
            text=f"测试回答：{question}；依据 {evidence[0].chunk.text}",
            mode="fake",
            model="fake-model",
        )

    def stream(
        self,
        question: str,
        evidence: list[RetrievedChunk],
    ):
        text = f"测试回答：{question}；依据 {evidence[0].chunk.text}"
        for start in range(0, len(text), 8):
            yield AnswerDelta(
                text=text[start : start + 8],
                mode="fake",
                model="fake-model",
            )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        reranker_enabled=False,
        llm_provider="none",
        model_local_files_only=True,
        retrieval_candidates=5,
    )


@pytest.fixture
def service(settings: Settings) -> RagService:
    return RagService(
        settings,
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        answerer=FakeAnswerer(),
    )


@pytest.fixture
def client(settings: Settings, service: RagService) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_rag_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
