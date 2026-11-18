from pydantic import BaseModel


class BookSummaryResponse(BaseModel):
    id: str
    title: str
    source_name: str
    character_count: int
    chunk_count: int
    created_at: str
    content_sha256: str


class BookListResponse(BaseModel):
    items: list[BookSummaryResponse]
    total: int


class UploadBookResponse(BaseModel):
    book: BookSummaryResponse
