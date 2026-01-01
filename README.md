# Coinbot

Stateless, automated cryptocurrency trading bot using MACD indicators.

## Tech Stack

- **Backend**: Python 3.12, uv package manager
- **Exchange**: Bitvavo API
- **Indicators**: MACD, RSI, MFI

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Bitvavo API credentials

## Quick Start

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
cp .env.example backend/.env
# Edit backend/.env with your Bitvavo API credentials
# Set BOT_ENABLED=true to enable trading
```

4. **Run tests**:
```bash
make test
```

5. **Run the trading bot**:
```bash
cd backend
uv run python -m coinbot_backend.main
```

See [backend/RUN_BOT.md](backend/RUN_BOT.md) for detailed bot documentation.

## Available Commands

Run `make help` to see all available commands:

```bash
make install      # Install all dependencies
make test         # Run all tests
make lint         # Run linting (ruff)
make format       # Format code (ruff)
make type-check   # Run type checking (mypy)
make clean        # Remove generated files
```

## Project Structure

```
coinbot/
├── backend/
│   ├── src/coinbot_backend/
│   │   ├── core/           # Constants, exceptions
│   │   ├── models/         # Data models (Candles, etc.)
│   │   └── services/       # Trading logic, indicators, Bitvavo client
│   ├── tests/
│   │   ├── unit/           # Unit tests
│   │   └── integration/    # Integration tests with Bitvavo API
│   └── pyproject.toml
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
