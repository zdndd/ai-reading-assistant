from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    use_gemini = settings.has_gemini_api_key and settings.llm_provider in (
        "auto",
        "gemini",
    )
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        llm_provider="gemini" if use_gemini else "extractive",
        generated_answers_enabled=use_gemini,
    )
