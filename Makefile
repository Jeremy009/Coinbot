.PHONY: help install run test lint format type-check clean ecr-build-and-push lambda-update lambda-publish

# AWS Configuration
AWS_ACCOUNT_ID := 080328315628
AWS_REGION ?= eu-central-1
ECR_REPO_NAME ?= coinbot
ECR_REPO_URI := $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME)
LAMBDA_FUNCTION ?= coinbot
IMAGE_TAG ?= latest

help:
	@echo "Available commands:"
	@echo ""
	@echo "  Development:"
	@echo "    make install          - Install all dependencies"
	@echo "    make run              - Run the trading bot"
	@echo "    make test             - Run all tests"
	@echo "    make lint             - Run linting (ruff)"
	@echo "    make format           - Format code (ruff)"
	@echo "    make type-check       - Run type checking (mypy)"
	@echo "    make clean            - Remove generated files"
	@echo ""
	@echo "  AWS Lambda Deployment:"
	@echo "    make lambda-publish   - Build, push to ECR, and update Lambda (all-in-one)"
	@echo "    make ecr-build-and-push - Build ARM64 container and push to ECR"
	@echo "    make lambda-update    - Update Lambda function with latest image"

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

# AWS Lambda deployment commands
ecr-build-and-push:
	@echo "Building ARM64 container for Lambda..."
	@echo "Target: $(ECR_REPO_URI):$(IMAGE_TAG)"
	docker buildx build --platform linux/arm64 --provenance=false --sbom=false -t $(ECR_REPO_URI):$(IMAGE_TAG) --push .
	@echo "Build complete!"

lambda-update:
	@echo "Updating Lambda function: $(LAMBDA_FUNCTION)"
	@echo "Image URI: $(ECR_REPO_URI):$(IMAGE_TAG)"
	aws lambda update-function-code \
		--function-name $(LAMBDA_FUNCTION) \
		--image-uri $(ECR_REPO_URI):$(IMAGE_TAG) \
		--region $(AWS_REGION) \
		--no-cli-pager
	@echo "Lambda function updated successfully!"

lambda-publish: ecr-build-and-push lambda-update

