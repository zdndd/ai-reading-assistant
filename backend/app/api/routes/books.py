from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_rag_service
from app.core.config import Settings, get_settings
from app.core.errors import DocumentTooLargeError
from app.domain.documents import BookSummary
from app.schemas.books import (
    BookListResponse,
    BookSummaryResponse,
    UploadBookResponse,
)
from app.services.rag import RagService

router = APIRouter(prefix="/books", tags=["books"])


def _book_response(book: BookSummary) -> BookSummaryResponse:
    return BookSummaryResponse(
        id=book.id,
        title=book.title,
        source_name=book.source_name,
        character_count=book.character_count,
        chunk_count=book.chunk_count,
        created_at=book.created_at,
        content_sha256=book.content_sha256,
    )


@router.post("", response_model=UploadBookResponse, status_code=201)
async def upload_book(
    service: Annotated[RagService, Depends(get_rag_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Form()] = None,
) -> UploadBookResponse:
    try:
        raw = await file.read(settings.upload_max_bytes + 1)
    finally:
        await file.close()

    if len(raw) > settings.upload_max_bytes:
        limit_mb = settings.upload_max_bytes / 1024 / 1024
        raise DocumentTooLargeError(f"文档超过 {limit_mb:.0f} MB 限制")

    book = await run_in_threadpool(
        service.create_book,
        file.filename or "",
        raw,
        title,
    )
    return UploadBookResponse(book=_book_response(book))


@router.get("", response_model=BookListResponse)
async def list_books(
    service: Annotated[RagService, Depends(get_rag_service)],
) -> BookListResponse:
    books = await run_in_threadpool(service.list_books)
    items = [_book_response(book) for book in books]
    return BookListResponse(items=items, total=len(items))


@router.get("/{book_id}", response_model=BookSummaryResponse)
async def get_book(
    book_id: str,
    service: Annotated[RagService, Depends(get_rag_service)],
) -> BookSummaryResponse:
    book = await run_in_threadpool(service.get_book, book_id)
    return _book_response(book)


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: str,
    service: Annotated[RagService, Depends(get_rag_service)],
) -> None:
    await run_in_threadpool(service.delete_book, book_id)
