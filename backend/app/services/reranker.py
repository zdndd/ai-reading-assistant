from __future__ import annotations

import threading
from typing import Protocol

from app.core.config import Settings
from app.core.errors import ModelUnavailableError
from app.domain.documents import RetrievedChunk


class Reranker(Protocol):
    def rank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]: ...


class PassThroughReranker:
    def rank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        del query
        return candidates[:top_k]


class CrossEncoderReranker:
    def __init__(self, settings: Settings) -> None:
        self.model_reference = settings.resolve_model_reference(settings.reranker_model)
        self.device = settings.embedding_device
        self.local_files_only = settings.model_local_files_only
        self.batch_size = settings.ingestion_batch_size
        self._model = None
        self._lock = threading.Lock()

    def rank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []

        model = self._get_model()
        pairs = [(query, candidate.chunk.text) for candidate in candidates]
        try:
            scores = model.predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise ModelUnavailableError(f"重排模型执行失败：{exc}") from exc

        reranked = [
            RetrievedChunk(
                chunk=candidate.chunk,
                retrieval_score=candidate.retrieval_score,
                rerank_score=float(score),
            )
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        reranked.sort(key=lambda item: item.rerank_score or float("-inf"), reverse=True)
        return reranked[:top_k]

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_reference,
                    device=self.device,
                    local_files_only=self.local_files_only,
                )
            except Exception as exc:
                raise ModelUnavailableError(
                    f"无法加载重排模型 {self.model_reference}：{exc}"
                ) from exc
        return self._model
