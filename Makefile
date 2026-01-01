.PHONY: help install run test lint format type-check clean docker-build docker-up docker-down docker-logs docker-shell

help:
	@echo "Available commands:"
	@echo ""
	@echo "  Development:"
	@echo "    make install      - Install all dependencies"
	@echo "    make run          - Run the trading bot"
	@echo "    make test         - Run all tests"
	@echo "    make lint         - Run linting (ruff)"
	@echo "    make format       - Format code (ruff)"
	@echo "    make type-check   - Run type checking (mypy)"
	@echo "    make clean        - Remove generated files"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build - Build Docker image"
	@echo "    make docker-up    - Start bot in Docker (detached)"
	@echo "    make docker-down  - Stop Docker container"
	@echo "    make docker-logs  - View Docker logs (live)"
	@echo "    make docker-shell - Access shell in running container"
	@echo "    make docker-restart - Restart Docker container"

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

run:
	cd backend && uv run python -m coinbot_backend.main

# Docker commands
docker-build:
	docker-compose build

docker-up:
	@mkdir -p data
	docker-compose up -d
	@echo "Bot started! View logs with: make docker-logs"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-shell:
	docker-compose exec coinbot /bin/bash

docker-restart:
	docker-compose restart

docker-status:
	docker-compose ps
