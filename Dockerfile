# Coinbot Trading Bot - Dockerfile
# Python 3.12 with uv package manager

FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager and add to PATH
ENV PATH="/root/.local/bin:$PATH"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set working directory
WORKDIR /app

# Copy project files
COPY backend/ /app/

# Install Python dependencies using uv
RUN uv sync --all-extras

# Create directory for persistent data
RUN mkdir -p /app/data

# Volume for persistent data (positions, trades, logs)
VOLUME ["/app/data"]

# Set the command to run the bot
CMD ["uv", "run", "python", "-m", "coinbot_backend.main"]
