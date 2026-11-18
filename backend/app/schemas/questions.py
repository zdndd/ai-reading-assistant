from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    book_id: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class EvidenceResponse(BaseModel):
    chunk_id: str
    book_id: str
    book_title: str
    chunk_index: int
    text: str
    retrieval_score: float
    rerank_score: float | None


class QuestionResponse(BaseModel):
    question: str
    answer: str
    mode: str
    model: str | None
    evidence: list[EvidenceResponse]
