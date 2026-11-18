from fastapi import APIRouter

from app.api.routes.books import router as books_router
from app.api.routes.questions import router as questions_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(books_router)
api_router.include_router(questions_router)
