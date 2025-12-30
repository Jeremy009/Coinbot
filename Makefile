.PHONY: help install test run lint format type-check build-docker run-docker clean

help:
	@echo "Available commands:"
	@echo "  make install      - Install all dependencies"
	@echo "  make test         - Run all tests"
	@echo "  make run          - Run backend locally"
	@echo "  make lint         - Run linting (ruff)"
	@echo "  make format       - Format code (ruff)"
	@echo "  make type-check   - Run type checking (mypy)"
	@echo "  make build-docker - Build Docker images"
	@echo "  make run-docker   - Run with docker-compose"
	@echo "  make clean        - Remove generated files"

install:
	cd backend && uv sync --all-extras

test:
	cd backend && uv run pytest

run:
	cd backend && uv run uvicorn coinbot_backend.main:app --reload --host 0.0.0.0 --port 8000

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .

type-check:
	cd backend && uv run mypy src/

build-docker:
	docker-compose build

run-docker:
	docker-compose up

stop-docker:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
