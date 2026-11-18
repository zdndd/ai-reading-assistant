from __future__ import annotations

import logging
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    logging.basicConfig(
        level=app_settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="基于向量召回、重排和证据引用的 AI 读书助手 API",
    )
    app.state.settings = app_settings
    app.state.rag_service = None
    app.state.rag_service_lock = threading.Lock()
    app.dependency_overrides[get_settings] = lambda: app_settings

    if app_settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "name": app_settings.app_name,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
