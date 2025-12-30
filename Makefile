.PHONY: help install test lint format type-check clean

help:
	@echo "Available commands:"
	@echo "  make install      - Install all dependencies"
	@echo "  make test         - Run all tests"
	@echo "  make lint         - Run linting (ruff)"
	@echo "  make format       - Format code (ruff)"
	@echo "  make type-check   - Run type checking (mypy)"
	@echo "  make clean        - Remove generated files"

install:
	cd backend && uv sync --all-extras

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .

type-check:
	cd backend && uv run mypy src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
