import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_rag_service
from app.core.errors import AppError
from app.domain.documents import RagStreamEvent, RetrievedChunk
from app.schemas.questions import (
    EvidenceResponse,
    QuestionRequest,
    QuestionResponse,
)
from app.services.rag import RagService

router = APIRouter(prefix="/questions", tags=["questions"])
logger = logging.getLogger(__name__)


def _evidence_response(item: RetrievedChunk) -> EvidenceResponse:
    return EvidenceResponse(
        chunk_id=item.chunk.chunk_id,
        book_id=item.chunk.book_id,
        book_title=item.chunk.book_title,
        chunk_index=item.chunk.chunk_index,
        text=item.chunk.text,
        retrieval_score=item.retrieval_score,
        rerank_score=item.rerank_score,
    )


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_data(item: RagStreamEvent) -> dict:
    data = dict(item.data)
    evidence = data.get("evidence")
    if isinstance(evidence, list):
        data["evidence"] = [
            _evidence_response(chunk).model_dump()
            for chunk in evidence
            if isinstance(chunk, RetrievedChunk)
        ]
    return data


@router.post("", response_model=QuestionResponse)
async def ask_question(
    payload: QuestionRequest,
    service: Annotated[RagService, Depends(get_rag_service)],
) -> QuestionResponse:
    evidence, answer = await run_in_threadpool(
        service.ask,
        payload.question,
        payload.book_id,
        payload.top_k,
    )
    return QuestionResponse(
        question=payload.question.strip(),
        answer=answer.text,
        mode=answer.mode,
        model=answer.model,
        evidence=[_evidence_response(item) for item in evidence],
    )


@router.post("/stream")
async def stream_question(
    payload: QuestionRequest,
    service: Annotated[RagService, Depends(get_rag_service)],
) -> StreamingResponse:
    def event_stream():
        try:
            for item in service.stream_answer(
                payload.question,
                payload.book_id,
                payload.top_k,
            ):
                yield _sse_event(item.event, _stream_data(item))
        except AppError as exc:
            yield _sse_event(
                "error",
                {
                    "code": exc.code,
                    "message": exc.message,
                },
            )
        except Exception:
            logger.exception("SSE question stream failed")
            yield _sse_event(
                "error",
                {
                    "code": "stream_failed",
                    "message": "流式回答失败，请稍后重试",
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
