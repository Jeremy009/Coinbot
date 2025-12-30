# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Coinbot is a modern, stateless cryptocurrency trading platform built with:
- **Backend**: Python 3.12, FastAPI, uv package manager
- **Exchange**: Bitvavo API integration
- **Infrastructure**: Docker, Docker Compose

## Tech Stack & Tools

- **Python 3.12**: Current stable release with modern features
- **uv**: Fast, modern package manager (10-100x faster than pip)
- **FastAPI**: High-performance async web framework
- **Pydantic**: Data validation and settings management
- **Ruff**: Fast Python linter and formatter
- **mypy**: Static type checking
- **pytest**: Testing framework

## Project Structure

```
coinbot/
├── backend/
│   ├── src/coinbot_backend/      # Main package (underscore naming)
│   │   ├── api/                  # FastAPI route handlers
│   │   ├── core/                 # Core utilities, constants, exceptions
│   │   ├── models/               # Pydantic models
│   │   └── services/             # Business logic (Bitvavo client)
│   ├── tests/                    # Tests (sibling to src/, not inside)
│   │   ├── unit/                 # Unit tests
│   │   └── integration/          # Integration tests
│   ├── pyproject.toml            # Dependencies and tool config
│   └── Dockerfile                # Multi-stage Docker build
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Template (committed)
├── docker-compose.yml            # Service orchestration
├── Makefile                      # Developer convenience commands
└── README.md
```

## Development Commands

All commands are available via the root-level `Makefile`:

```bash
make install      # Install dependencies with uv
make run          # Run backend locally (http://localhost:8000)
make test         # Run all tests with pytest
make lint         # Check code with ruff
make format       # Auto-format code with ruff
make type-check   # Run mypy type checking
make build-docker # Build Docker images
make run-docker   # Run with docker-compose
```

## Key Design Patterns

### Configuration Management
- All configuration in `backend/src/coinbot_backend/config.py`
- Uses `pydantic-settings` to load from environment variables
- **CRITICAL**: `.env` file must be in `backend/` directory (where code runs), not project root
- Settings loaded from `.env` file automatically
- Access via `from coinbot_backend.config import settings`

### API Rate Limiting
- All Bitvavo API calls use `@limit_api_calls` decorator
- Prevents blacklisting by checking remaining calls (max 1000/min)
- Raises `CoinbotRateLimitError` if below threshold (100 calls)
- **When testing**: Mock `get_remaining_limit()` to avoid exhausting API quota

### Singleton Pattern
- BitvavoClient accessed via `get_bitvavo_client()` function
- Single instance shared across application
- Initialized lazily on first access

### FastAPI Structure
- Routes organized by domain in `api/` directory
- `/health` and `/ready` endpoints for health checks
- `/api/v1/*` prefix for versioned trading endpoints
- Automatic OpenAPI docs at `/docs`

## Trading Bot Architecture

### MACD Trading Strategy
The bot (`services/macd_bot.py`) implements a **stateless MACD-based trading strategy**:

1. **Symbol Analysis** (`get_promising_symbols`):
   - Scans all exchange symbols for opportunities
   - Filters by: 24h positive growth, minimum volume threshold, BUY signal from MACD
   - Returns ranked list by MACD strength

2. **Position Management**:
   - `analyse_existing_positions`: Checks owned symbols, sells if MACD signals SELL
   - `open_new_positions`: Opens new positions up to configured limit

3. **Configuration** (via `.env`):
   - `BOT_ENABLED`: Enable/disable bot execution
   - `BOT_UPDATE_INTERVAL`: Minutes between bot runs
   - `BOT_NUM_POSITIONS`: Maximum concurrent positions
   - `BOT_VOLUME_LIMIT`: Minimum 24h volume threshold (EUR)
   - `BOT_MACD_*`: MACD parameters (time resolution, periods)

### Technical Indicators (`services/indicators.py`)
- **MACD**: Moving Average Convergence Divergence (default: 12/39/9 periods)
- **RSI**: Relative Strength Index (default: 14 periods)
- **MFI**: Money Flow Index (default: 14 periods)
- All return pandas DataFrames with indicator columns added

### Trading Signals (`services/signals.py`)
- `TradebotAction` enum: BUY, HOLD, SELL
- `macd_signal()`: Analyzes MACD histogram momentum
  - BUY: Positive momentum and building (3+ increasing bars)
  - SELL: Negative momentum OR positive but decreasing (4+ decreasing bars)
  - HOLD: Positive momentum but not building
- `rsi_signal()`: RSI-based signals (oversold < 30, overbought > 70)

### OHLCV Candles Model (`models/candles.py`)
- Stores financial time series: Open, High, Low, Close, Volume
- Validates data consistency
- Computes timespan metrics
- `as_dataframe()`: Converts to pandas with caching for indicators
- Supports both "older-to-newer" and "newer-to-older" ordering

## Running the Application

### First Time Setup

1. Install uv (if needed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Copy `.env.example` to `.env` and add your Bitvavo API credentials

3. Install dependencies:
```bash
make install
```

### Local Development

```bash
make run
```

Backend runs at `http://localhost:8000` with auto-reload enabled.

### Docker Deployment

```bash
make run-docker
```

### Testing

```bash
make test                                            # Run all tests (from project root)
cd backend && uv run pytest                          # Run all tests (from backend/)
cd backend && uv run pytest tests/unit/              # Unit tests only
cd backend && uv run pytest tests/integration/       # Integration tests only
cd backend && uv run pytest tests/unit/test_candles.py::test_candles_creation  # Single test
cd backend && uv run pytest -v -s                    # Verbose with print output
cd backend && uv run pytest -k "candles"             # Tests matching pattern
```

### Testing Best Practices

**Unit Tests** (`tests/unit/`):
- Use **mock data** instead of API calls
- Fast execution (milliseconds)
- Example: `test_candles.py` creates candles with hardcoded timestamps/prices

**Integration Tests** (`tests/integration/`):
- Make **real API calls** to Bitvavo
- Requires valid `.env` with API credentials in `backend/` directory
- Slower execution (seconds to minutes)
- **IMPORTANT**: Mock `get_remaining_limit()` when testing the rate limiter decorator
  ```python
  def test_limit_api_calls_decorator(self, bitvavo_client, monkeypatch):
      monkeypatch.setattr(bitvavo_client, "get_remaining_limit", lambda: 50)
      with pytest.raises(CoinbotRateLimitError):
          bitvavo_client.get_total_deposited()
  ```
  This avoids exhausting the API quota (1000 calls/min) during test runs.

**Test Fixtures** (`tests/conftest.py`):
- `client`: FastAPI TestClient for API endpoint testing
- `mock_bitvavo_client`: Mocked Bitvavo client to avoid real API calls
- Module-scoped fixtures share instances across test class

## Bitvavo API Integration

### Rate Limits
- **1000 calls per minute** maximum
- `get_remaining_limit()` returns current remaining calls
- All API methods decorated with `@limit_api_calls`
- Raises `CoinbotRateLimitError` when < 100 calls remaining

### Candle Data Retrieval
- **Maximum 1440 candles per request** (Bitvavo API limit)
- `get_candles()` handles pagination automatically with progress bar
- Time resolutions: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d (see `TIME_RESOLUTIONS`)
- Time spans: 1h to 5y (see `TIME_SPANS`)
- Missing candles may occur during low-volume periods

### Symbol Handling
- Symbols are base currencies (e.g., "BTC", "ETH", not "BTC-EUR")
- Market pairs always appended with "-EUR" internally
- **IMPORTANT**: Some symbols become deprecated (e.g., "REP" no longer exists)
  - Always verify symbols exist before using in tests
  - Use `get_available_symbols()` for current list
  - Common test symbols: "BTC", "ETH", "LINK", "UNI", "DOT"

### Account Data
- `get_total_deposited()`: Sum of all deposits minus fees
- `get_total_withdrawn()`: Sum of all withdrawals minus fees
- `get_total_gains()`: Current balance - deposited + withdrawn
- `get_available_funds()`: EUR balance available for trading
- `get_owned_symbols()`: Symbols with non-zero balance

## Important Notes

- **No requirements.txt**: Use `pyproject.toml` + `uv.lock` instead
- **Tests location**: Tests are siblings to `src/`, not inside the package
- **Package naming**: Import as `coinbot_backend` (underscore), project name is `coinbot-backend` (hyphen)
- **Type hints**: Full type annotations required (enforced by mypy strict mode)
- **Python path**: Set via `PYTHONPATH=/app/src` in Docker, automatic when using `uv run`
- **.env location**: Must be in `backend/` directory, NOT project root (common mistake)

## API Endpoints

- `GET /` - Root endpoint with API info
- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /api/v1/balance` - Account balance information
- `GET /api/v1/symbols` - List available trading symbols
- `GET /api/v1/symbols/{symbol}` - Get specific symbol info

## Exception Handling

All custom exceptions inherit from `CoinbotException` base class:

- `CoinbotAPIError`: General API errors
- `CoinbotRateLimitError`: Rate limit exceeded (alias: `CoinbotExceededNumAPICallsError`)
- `CoinbotInvalidSymbolError`: Invalid trading symbol
- `CoinbotUnexpectedValueError`: Unexpected value encountered (e.g., symbol doesn't exist)
- `CoinbotUnexpectedTypeError`: Type mismatch errors

**Legacy Compatibility**: Some exceptions have aliases for backwards compatibility with old code
- `CoinbotBaseError` → `CoinbotException`
- `CoinbotExceededNumAPICallsError` → `CoinbotRateLimitError`

## Adding New Features

1. **New API endpoint**: Add route in `backend/src/coinbot_backend/api/`
2. **New data model**: Add in `backend/src/coinbot_backend/models/`
3. **New service**: Add in `backend/src/coinbot_backend/services/`
4. **New exception**: Add in `backend/src/coinbot_backend/core/exceptions.py`
5. **Always write tests**: Add corresponding tests in `backend/tests/`

**Example: Adding a new Bitvavo API method**
```python
@limit_api_calls  # Always use this decorator
def get_new_data(self, symbol: str) -> dict[str, Any]:
    """Clear docstring explaining what this does."""
    if symbol not in self.available_symbols:
        raise CoinbotInvalidSymbolError(f"Symbol {symbol} not available")
    return self._client.someMethod(symbol + "-EUR")
```

## Code Quality

The project enforces:
- **Ruff**: Fast linting and formatting (replaces black, isort, flake8)
- **mypy**: Strict type checking
- **pytest**: Comprehensive test coverage

Run all checks before committing:
```bash
make format      # Auto-fix formatting issues
make lint        # Check for remaining issues
make type-check  # Verify type annotations
make test        # Ensure tests pass
```
