from __future__ import annotations

import threading
from typing import Protocol

from app.core.config import Settings
from app.core.errors import ModelUnavailableError


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, settings: Settings) -> None:
        self.model_reference = settings.resolve_model_reference(settings.embedding_model)
        self.device = settings.embedding_device
        self.local_files_only = settings.model_local_files_only
        self.batch_size = settings.ingestion_batch_size
        self._model = None
        self._lock = threading.Lock()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._encode(texts)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        embeddings = self._encode([text])
        if not embeddings:
            raise ModelUnavailableError("查询向量生成失败")
        return embeddings[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        try:
            vectors = model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        except Exception as exc:
            raise ModelUnavailableError(f"文本向量模型执行失败：{exc}") from exc
        return [[float(value) for value in vector] for vector in vectors]

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    self.model_reference,
                    device=self.device,
                    local_files_only=self.local_files_only,
                )
                self._model.max_seq_length = 512
            except Exception as exc:
                raise ModelUnavailableError(
                    f"无法加载向量模型 {self.model_reference}：{exc}"
                ) from exc
        return self._model
