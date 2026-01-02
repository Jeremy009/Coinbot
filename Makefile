.PHONY: help install run test lint format type-check clean docker-build docker-up docker-down docker-logs docker-shell lambda-build lambda-push lambda-deploy lambda-publish

# AWS Configuration
AWS_ACCOUNT_ID ?= $(shell aws sts get-caller-identity --query Account --output text 2>/dev/null)
AWS_REGION ?= eu-central-1
ECR_REPO ?= $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/coinbot
LAMBDA_FUNCTION ?= coinbot

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
	@echo ""
	@echo "  AWS Lambda Deployment:"
	@echo "    make lambda-publish - Build, push to ECR, and update Lambda (all-in-one)"
	@echo "    make lambda-build   - Build ARM64 container for Lambda"
	@echo "    make lambda-push    - Push container to ECR"
	@echo "    make lambda-deploy  - Update Lambda function with latest image"

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

# AWS Lambda deployment commands
lambda-build:
	@echo "Building ARM64 container for Lambda..."
	docker buildx build --platform linux/arm64 --provenance=false --sbom=false -t $(ECR_REPO):latest .
	@echo "Build complete!"

lambda-push:
	@echo "Authenticating with ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	@echo "Pushing image to ECR..."
	docker buildx build --platform linux/arm64 --provenance=false --sbom=false -t $(ECR_REPO):latest --push .
	@echo "Push complete!"

lambda-deploy:
	@echo "Updating Lambda function: $(LAMBDA_FUNCTION)..."
	aws lambda update-function-code \
		--function-name $(LAMBDA_FUNCTION) \
		--image-uri $(ECR_REPO):latest \
		--region $(AWS_REGION)
	@echo "Waiting for Lambda update to complete..."
	@aws lambda wait function-updated --function-name $(LAMBDA_FUNCTION) --region $(AWS_REGION)
	@echo "Lambda function updated successfully!"

lambda-publish: lambda-push lambda-deploy
	@echo ""
	@echo "Deployment complete! Test with:"
	@echo "  aws lambda invoke --function-name $(LAMBDA_FUNCTION) --region $(AWS_REGION) response.json"
