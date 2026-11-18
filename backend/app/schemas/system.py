from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    llm_provider: str
    generated_answers_enabled: bool


class ErrorResponse(BaseModel):
    code: str
    message: str
