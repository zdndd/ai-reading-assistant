from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI 读书助手"
    app_env: str = "development"
    log_level: str = "INFO"

    data_dir: Path = PROJECT_ROOT / "data"
    upload_max_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    chunk_size: int = Field(default=300, ge=100, le=4000)
    chunk_overlap: int = Field(default=50, ge=0)
    max_chunks_per_book: int = Field(default=10_000, gt=0)
    ingestion_batch_size: int = Field(default=64, gt=0)
    retrieval_candidates: int = Field(default=10, ge=1, le=100)

    embedding_model: str = "../rag_mark/models/text2vec-base-chinese"
    embedding_device: str | None = None
    reranker_model: str = "../rag_mark/models/mmarco-mMiniLMv2-L12-H384-v1"
    reranker_enabled: bool = True
    model_local_files_only: bool = True

    llm_provider: Literal["auto", "gemini", "none"] = "auto"
    gemini_api_key: SecretStr | None = None
    gemini_models: str = "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.7-flash"
    gemini_temperature: float = Field(default=0.1, ge=0, le=2)
    gemini_timeout_seconds: float = Field(default=60, gt=0)

    cors_origins: str = "http://localhost:4200,http://127.0.0.1:4200"

    @field_validator("data_dir", mode="after")
    @classmethod
    def resolve_data_dir(cls, value: Path) -> Path:
        path = value.expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @model_validator(mode="after")
    def validate_chunking(self) -> Settings:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP 必须小于 CHUNK_SIZE")
        return self

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def books_dir(self) -> Path:
        return self.data_dir / "books"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gemini_model_candidates(self) -> list[str]:
        return [model.strip() for model in self.gemini_models.split(",") if model.strip()]

    @property
    def has_gemini_api_key(self) -> bool:
        if self.gemini_api_key is None:
            return False
        return bool(self.gemini_api_key.get_secret_value().strip())

    def resolve_model_reference(self, reference: str) -> str:
        path = Path(reference).expanduser()
        if path.is_absolute():
            return str(path)

        project_candidate = (PROJECT_ROOT / path).resolve()
        if project_candidate.exists():
            return str(project_candidate)

        cwd_candidate = (Path.cwd() / path).resolve()
        if cwd_candidate.exists():
            return str(cwd_candidate)

        if reference.startswith((".", "/")) or path.parts[:1] == ("models",):
            return str(project_candidate)
        return reference


@lru_cache
def get_settings() -> Settings:
    return Settings()
