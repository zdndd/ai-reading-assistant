.PHONY: dev frontend-dev test lint build frontend-build

dev:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend-dev:
	cd frontend && npm start

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .

frontend-build:
	cd frontend && npm run build

build: frontend-build
