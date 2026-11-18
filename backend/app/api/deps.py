import threading

from fastapi import Request

from app.services.rag import RagService


def get_rag_service(request: Request) -> RagService:
    service = getattr(request.app.state, "rag_service", None)
    if service is not None:
        return service

    lock: threading.Lock = request.app.state.rag_service_lock
    with lock:
        service = getattr(request.app.state, "rag_service", None)
        if service is None:
            service = RagService(request.app.state.settings)
            request.app.state.rag_service = service
        return service
