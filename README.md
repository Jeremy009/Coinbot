# Coinbot

Stateless, automated cryptocurrency trading platform.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, uv package manager
- **Infrastructure**: Docker, Docker Compose

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker and Docker Compose (optional, for containerized deployment)

## Quick Start

### Local Development

1. **Install uv** (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Install dependencies**:
```bash
make install
```

3. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

4. **Run the backend**:
```bash
make run
```

The API will be available at `http://localhost:8000`

### Docker Deployment

1. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

2. **Build and run with Docker Compose**:
```bash
make run-docker
```

## Available Commands

Run `make help` to see all available commands:

```bash
make install      # Install all dependencies
make test         # Run all tests
make run          # Run backend locally
make lint         # Run linting (ruff)
make format       # Format code (ruff)
make type-check   # Run type checking (mypy)
make build-docker # Build Docker images
make run-docker   # Run with docker-compose
```

## Project Structure

```
coinbot/
├── backend/              # Python backend service
│   ├── src/
│   │   └── coinbot_backend/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── docker-compose.yml
├── Makefile
└── README.md
```

## Development

### Running Tests

```bash
make test
```

### Code Quality

```bash
make lint        # Check for linting issues
make format      # Auto-format code
make type-check  # Type checking with mypy
```

## License

MIT
