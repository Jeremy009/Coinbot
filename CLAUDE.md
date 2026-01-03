# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Style Guidelines

**IMPORTANT: DO NOT USE EMOJIS**
- Never use emojis in code, comments, log messages, or documentation
- Use plain text for all output and logging
- Keep all messages professional and text-based

## Project Overview

Coinbot is a stateless cryptocurrency trading bot built with:
- **Backend**: Python 3.12, uv package manager
- **Exchange**: Bitvavo API integration
- **Strategy**: MACD-based trading signals

## Tech Stack & Tools

- **Python 3.12**: Current stable release with modern features
- **uv**: Fast, modern package manager (10-100x faster than pip)
- **Pydantic**: Data validation and settings management
- **Ruff**: Fast Python linter and formatter
- **mypy**: Static type checking
- **pytest**: Testing framework

## Project Structure

```
coinbot/
├── backend/
│   ├── src/coinbot_backend/      # Main package (underscore naming)
│   │   ├── core/                 # Core utilities, constants, exceptions
│   │   ├── models/               # Data models (Candles, etc.)
│   │   └── services/             # Trading logic, indicators, Bitvavo client, S3 storage
│   ├── tests/                    # Tests (sibling to src/, not inside)
│   │   ├── unit/                 # Unit tests
│   │   └── integration/          # Integration tests with Bitvavo API
│   └── pyproject.toml            # Dependencies and tool config
├── backend/.env                  # Environment variables (gitignored)
├── .env.example                  # Template (committed)
├── Makefile                      # Developer convenience commands
└── README.md
```

## Development Commands

All commands are available via the root-level `Makefile`:

```bash
make install      # Install dependencies with uv
make test         # Run all tests with pytest
make lint         # Check code with ruff
make format       # Auto-format code with ruff
make type-check   # Run mypy type checking
make clean        # Remove generated files
```

## Key Design Patterns

### Configuration Management
- All configuration in `backend/src/coinbot_backend/config.py`
- Uses `pydantic-settings` to load from environment variables
- **CRITICAL**: `.env` file must be in `backend/` directory (where code runs), not project root
- Settings loaded from `.env` file automatically
- Access via `from coinbot_backend.config import settings`

### S3 Storage
- All bot data (positions, trades, logs, charts) is stored in AWS S3, not on the filesystem
- Uses `services/s3_storage.py` for S3 operations
- **Authentication methods** (in order of preference):
  1. **AWS Credential Chain** (recommended): AWS CLI, IAM role, environment variables
  2. **Explicit credentials**: Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`
- **Required settings** in `.env`:
  - `AWS_REGION` - AWS region (e.g., `eu-central-1`)
  - `S3_BUCKET_NAME` - S3 bucket name for storing data
- **Data locations**:
  - Positions: `s3://{bucket}/positions.json`
  - Trade logs: `s3://{bucket}/trades.json`
  - Run folders: `s3://{bucket}/runs/YYYYMMDD_HHMM/`
    - Application logs: `s3://{bucket}/runs/YYYYMMDD_HHMM/logs.txt`
    - Technical analysis charts:
      - `H_SYMBOL.png`: Held positions (with green buy marker)
      - `S_SYMBOL.png`: Sold positions
      - `B_SYMBOL.png`: Bought positions
      - `X_SYMBOL.png`: Rejected symbols (passed pre-filter, failed strategy)
- **Logging destinations** (simultaneous):
  1. **Console** (stdout/stderr) - real-time monitoring, CloudWatch integration
  2. **S3** (runs/YYYYMMDD_HHMM/logs.txt) - persistent storage and analysis
- **Chart generation**: Every symbol analyzed generates a technical analysis chart showing all indicators, uploaded to S3 for later review

**S3 operations are logged:**
- Upload operations: "Uploading to S3: s3://bucket/key"
- Download operations: "Downloading from S3: s3://bucket/key"
- Success messages: "Successfully uploaded/downloaded"
- Error messages: "Failed to upload/download"

**Testing S3 connection:**
```bash
cd backend && uv run python test_s3_connection.py
```

**Testing S3 logging:**
```bash
cd backend && uv run python test_s3_logging.py
```

### API Rate Limiting
- All Bitvavo API calls use `@limit_api_calls` decorator
- Prevents blacklisting by checking remaining calls (max 1000/min)
- Raises `CoinbotRateLimitError` if below threshold (100 calls)
- **When testing**: Mock `get_remaining_limit()` to avoid exhausting API quota

### Singleton Pattern
- BitvavoClient accessed via `get_bitvavo_client()` function
- Single instance shared across application
- Initialized lazily on first access

### Dry-Run Mode (Paper Trading)
- **HIGHLY RECOMMENDED** for testing before using real money
- Enable with `BOT_DRY_RUN=true` in `.env` (enabled by default)
- Simulates all buy/sell orders without hitting the exchange
- Uses real market data (prices, candles, symbols) but fake balances
- Tracks simulated EUR and crypto balances internally
- Simulates Bitvavo taker fees (default 0.25% for market orders, configurable)
- All logs clearly marked with "DRY-RUN" prefix to indicate dry-run operations
- Position tracking and trade logging work identically to live mode
- Set initial balance with `BOT_DRY_RUN_INITIAL_BALANCE` (default: €1000)
- Configure fee rate with `BOT_DRY_RUN_FEE_RATE` (default: 0.0025 = 0.25%)

**Bitvavo Fee Structure:**
- **Taker fee: 0.25%** (standard tier, market orders always use taker fee)
- **Maker fee: 0.15%** (limit orders that add liquidity - not currently used)
- Volume-based tiers: Fees decrease with 30-day volume (down to 0.03% maker / 0.04% taker)
- The bot uses market orders → always pays taker fee

**Testing the bot:**
1. Set `BOT_DRY_RUN=true` in `backend/.env`
2. Run: `cd backend && uv run python -m coinbot_backend.main`
3. Watch logs to see simulated trades
4. Check S3 for results:
   - `s3://bucket/positions.json` - Current positions
   - `s3://bucket/trades.json` - Trade history
   - `s3://bucket/runs/YYYYMMDD_HHMM/` - Run logs and charts
5. Test script: `cd backend && uv run python test_dry_run.py`

**Going live (USE EXTREME CAUTION):**
1. Thoroughly test in dry-run mode for at least 1-2 weeks
2. Verify strategies are working as expected
3. Set `BOT_DRY_RUN=false` in `backend/.env`
4. Start with small allocation (reduce `BOT_MAX_ALLOCATION_PERCENT`)
5. Monitor closely for first few days

## Trading Bot Architecture

### Multi-Strategy Trading Bot (`main.py`)
The bot (`main.py`) implements a **two-tier trading strategy with position tracking**:

**Key Features:**
- Persistent position tracking stored in S3 (`positions.json`)
- Complete trade logging with P/L calculations stored in S3 (`trades.json`)
- Technical analysis chart generation for all analyzed symbols (H_, S_, B_, X_ charts)
- Run-based organization with timestamped folders (runs/YYYYMMDD_HHMM/)
- Single iteration execution (designed for scheduled/cron jobs)
- Two-tier strategy: Fast MACD check → Advanced multi-strategy confluence
- Risk management: Only uses configured % of available funds (default: 5%)

**Trading Flow:**

1. **Finding Opportunities** (`find_opportunities`):
   - Scans all exchange symbols
   - Filters: 24h positive growth, minimum volume threshold, MACD BUY signal
   - Returns top N opportunities ranked by volume

2. **Position Management**:
   - **Tier 1 (Fast MACD)**: Quick momentum check for existing positions
     - SELL signal → Immediately sell
     - BUY signal → Keep holding
     - HOLD signal → Go to Tier 2
   - **Tier 2 (Multi-strategy confluence)**: Advanced analysis if MACD is unclear
     - Uses 3 strategies: RSI+MACD, EMA crossover, Bollinger mean reversion
     - SELL/STRONG_SELL with >65% confidence → Sell
     - Otherwise → Keep holding

3. **Configuration** (via `.env`):
   - `BOT_ENABLED`: Enable/disable bot execution
   - `BOT_DRY_RUN`: Enable paper trading mode (default: true, **RECOMMENDED**)
   - `BOT_DRY_RUN_INITIAL_BALANCE`: Starting EUR for simulated trading (default: €1000)
   - `BOT_UPDATE_INTERVAL`: Minutes between bot runs
   - `BOT_NUM_POSITIONS`: Maximum concurrent positions
   - `BOT_MAX_ALLOCATION_PERCENT`: Percentage of available funds to use for trading (default: 5.0%)
   - `BOT_VOLUME_LIMIT`: Minimum 24h volume threshold (EUR)
   - `BOT_MACD_*`: MACD parameters (time resolution, periods)

### Trading Strategies (`services/trading_strategies.py`)
**Unified module consolidating indicators, signals, and strategies**

**Key Types:**
- `Signal` enum: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
- `TradeSignal` dataclass: Contains signal, confidence, reason, stop_loss, take_profit, indicators

**Indicator Calculators (private helpers):**
- `calculate_macd()`: Moving Average Convergence Divergence
- `calculate_rsi()`: Relative Strength Index
- `calculate_mfi()`: Money Flow Index
- `calculate_ema()`, `calculate_sma()`: Moving averages
- `calculate_bollinger_bands()`: Volatility bands
- `calculate_atr()`: Average True Range

**Strategy Functions (uniform interface):**
All strategies have signature: `strategy_<name>(candles: OHLCVCandles | pd.DataFrame, **params) -> TradeSignal`
- `strategy_macd_simple()`: Fast MACD momentum signals
- `strategy_rsi_simple()`: Overbought/oversold detection
- `strategy_rsi_macd()`: Combined RSI + MACD (73% win rate)
- `strategy_ema_crossover()`: Golden/Death cross signals
- `strategy_bollinger_mean_reversion()`: Mean reversion trades
- `strategy_bollinger_squeeze_breakout()`: Volatility breakout detection
- `strategy_multi_confluence()`: Multi-indicator confluence (highest confidence)

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

### Running the Bot

The trading bot can be run directly:
```bash
cd backend && uv run python -m coinbot_backend.main
```

Ensure `BOT_ENABLED=true` in your `.env` file and AWS credentials are configured.

The bot will:
- Load existing positions from S3 (`positions.json`)
- Evaluate all positions using two-tier strategy
- Look for new opportunities (up to `BOT_NUM_POSITIONS`)
- Only use `BOT_MAX_ALLOCATION_PERCENT` of available funds
- Save positions and log all trades to S3
- **Run once and exit** (designed for scheduled execution via cron/Lambda/ECS Scheduled Tasks)

**Scheduling the bot:**
The bot now runs a single iteration and exits. You should schedule it using:
- **AWS Lambda** with EventBridge (e.g., every 2 hours)
- **AWS ECS Scheduled Tasks** (e.g., every 2 hours)
- **Cron job** on a server (e.g., `0 */2 * * *` for every 2 hours)
- **Kubernetes CronJob**

### Technical Analysis & Visualization

The bot includes a comprehensive technical analysis plotting tool that visualizes all indicators used for trading decisions:

**Features:**
- Candlestick chart with EMA overlays (12, 50, 200 periods)
- Bollinger Bands (20-period, 2 standard deviations)
- RSI indicator with overbought/oversold levels
- MACD with signal line and histogram
- Trading volume bars with automatic scaling (EUR, k EUR, M EUR)
- Strategy signal and confidence in title
- Time labels at 00h00 and 12h00 for readability
- Consistent unit formatting with square brackets [EUR]

**Usage:**
```bash
cd backend

# Display interactive chart
uv run python example_technical_analysis_plot.py BTC

# Save to file
uv run python example_technical_analysis_plot.py BTC --save

# Custom parameters
uv run python example_technical_analysis_plot.py ETH --resolution 4h --span 1m --output eth_analysis.png
```

**Available parameters:**
- `symbol`: Trading symbol (BTC, ETH, LINK, etc.)
- `--resolution`: Time resolution (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d)
- `--span`: Time span (1h, 4h, 12h, 1d, 1w, 2w, 1m, 2m, 4m, 6m, 1y, 2y, 5y)
- `--save`: Save chart to file instead of displaying
- `--output`: Custom output file path

**Programmatic usage:**
```python
from datetime import datetime
from coinbot_backend.services.bitvavo_client import get_bitvavo_client
from coinbot_backend.services.technical_analysis_plot import plot_technical_analysis

client = get_bitvavo_client()
candles = client.get_candles("BTC", "1h", "2w")

# Show interactive plot
plot_technical_analysis(candles, show=True)

# Save to file
plot_technical_analysis(candles, save_path="btc_analysis.png")

# Mark buy datetime with green vertical line
buy_time = datetime(2026, 1, 1, 12, 0)
plot_technical_analysis(candles, buy_datetime=buy_time, show=True)

# Get PNG bytes for S3 upload
chart_bytes = plot_technical_analysis(candles, return_bytes=True)
```

This tool is invaluable for:
- Understanding why the bot made buy/sell decisions
- Debugging strategy behavior
- Manual verification of trading signals
- Analyzing market conditions before trading

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
- **IMPORTANT**: Mock `get_remaining_limit()` and `time.sleep()` when testing the rate limiter
  ```python
  def test_limit_api_calls_decorator(self, bitvavo_client, monkeypatch):
      # Mock to simulate low remaining calls, then high after reset
      call_count = {"count": 0}
      monkeypatch.setattr(
          bitvavo_client, "get_remaining_limit",
          lambda: 50 if call_count["count"] == 0 else 950
      )
      monkeypatch.setattr(time, "sleep", lambda s: None)  # Skip actual wait
      bitvavo_client.get_total_deposited()  # Should wait, then proceed
  ```
  This tests the wait/retry logic without exhausting API quota or waiting 60s.

**Test Fixtures** (`tests/conftest.py`):
- `mock_bitvavo_client`: Mocked Bitvavo client to avoid real API calls
- Module-scoped fixtures share instances across test class

## Bitvavo API Integration

### Rate Limits
- **1000 calls per minute** maximum
- `get_remaining_limit()` returns current remaining calls
- All API methods decorated with `@limit_api_calls`
- Automatically waits 60 seconds for rate limit reset when < 100 calls remaining

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
- **.env location**: Must be in `backend/` directory, NOT project root (common mistake)

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

1. **New data model**: Add in `backend/src/coinbot_backend/models/`
2. **New service**: Add in `backend/src/coinbot_backend/services/`
3. **New exception**: Add in `backend/src/coinbot_backend/core/exceptions.py`
4. **Always write tests**: Add corresponding tests in `backend/tests/`

**Example: Adding a new Bitvavo API method**
```python
@limit_api_calls  # Always use this decorator
def get_new_data(self, symbol: str) -> dict[str, Any]:
    """Clear docstring explaining what this does."""
    if symbol not in self.available_symbols:
        raise CoinbotInvalidSymbolError(f"Symbol {symbol} not available")
    return self._client.someMethod(symbol + "-EUR")
```

## AWS Lambda Deployment

The bot is designed to run as a containerized Lambda function on AWS, scheduled to run periodically (e.g., every 2 hours).

### Prerequisites

- AWS CLI configured with appropriate credentials
- ECR repository created (e.g., `coinbot`)
- S3 bucket for storing bot data (positions, trades, logs)
- IAM role for Lambda with S3 access permissions
- Bitvavo API credentials

### Dockerfile

The project includes a Lambda-compatible Dockerfile at the root:
- Uses `public.ecr.aws/lambda/python:3.12` base image
- Installs dependencies with pip
- Copies source code to `${LAMBDA_TASK_ROOT}`
- Sets proper file permissions with `chmod -R 755`
- Handler: `lambda_handler.handler`

**Key fixes for Lambda compatibility:**
- Version handling: Uses hardcoded `__version__` instead of `importlib.metadata.version()` since package isn't installed
- Permissions: Explicit `chmod -R 755` to avoid permission denied errors
- Dependencies: Quoted package specs to prevent shell redirection issues

### Build and Push to ECR

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region eu-central-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-central-1.amazonaws.com

# Build for ARM64 (cost-effective for Lambda)
docker buildx build --platform linux/arm64 --provenance=false --sbom=false \
  -t <account-id>.dkr.ecr.eu-central-1.amazonaws.com/coinbot:latest --push .
```

**Important flags:**
- `--platform linux/arm64`: Lambda ARM64 architecture (cheaper than x86)
- `--provenance=false --sbom=false`: Required for Lambda compatibility
- `--push`: Push directly to ECR

### Create Lambda Function

```bash
aws lambda create-function \
  --function-name coinbot \
  --package-type Image \
  --code ImageUri=<account-id>.dkr.ecr.eu-central-1.amazonaws.com/coinbot:latest \
  --role arn:aws:iam::<account-id>:role/coinbot-lambda-role \
  --architectures arm64 \
  --memory-size 1024 \
  --timeout 900 \
  --region eu-central-1
```

**Configuration notes:**
- Memory: 1024 MB (enough for pandas/numpy operations)
- Timeout: 900 seconds (15 minutes) - bot needs time to analyze symbols
- Architecture: ARM64 (better price/performance)

### Update Existing Function

```bash
aws lambda update-function-code \
  --function-name coinbot \
  --image-uri <account-id>.dkr.ecr.eu-central-1.amazonaws.com/coinbot:latest \
  --region eu-central-1
```

### Configure Environment Variables

**Via AWS Console:**
Lambda > coinbot > Configuration > Environment variables > Edit

**Via AWS CLI:**
```bash
aws lambda update-function-configuration \
  --function-name coinbot \
  --environment "Variables={
    BOT_ENABLED=true,
    BOT_DRY_RUN=true,
    BOT_DRY_RUN_INITIAL_BALANCE=1000,
    BOT_NUM_POSITIONS=3,
    BOT_MAX_ALLOCATION_PERCENT=5.0,
    BOT_VOLUME_LIMIT=100000,
    S3_BUCKET_NAME=your-bucket-name,
    BITVAVO_API_KEY=your-api-key,
    BITVAVO_API_SECRET=your-api-secret
  }" \
  --region eu-central-1
```

**Note:** Do NOT set `AWS_REGION` - it's reserved by Lambda. The region is available via `AWS_REGION` environment variable automatically.

### IAM Permissions

The Lambda execution role needs:

**S3 Access:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name/*",
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

**CloudWatch Logs (automatically attached):**
- `arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`

### Schedule with EventBridge

Run the bot every 2 hours:

```bash
# Create schedule rule
aws events put-rule \
  --name coinbot-schedule \
  --schedule-expression "rate(2 hours)" \
  --region eu-central-1

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name coinbot \
  --statement-id coinbot-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:eu-central-1:<account-id>:rule/coinbot-schedule \
  --region eu-central-1

# Add Lambda as target
aws events put-targets \
  --rule coinbot-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:eu-central-1:<account-id>:function:coinbot" \
  --region eu-central-1
```

### Testing

**Invoke manually:**
```bash
aws lambda invoke --function-name coinbot --region eu-central-1 response.json
cat response.json
```

**Expected response (with dry-run enabled):**
```json
{
  "statusCode": 200,
  "body": "{\"message\": \"Bot iteration completed successfully\", \"version\": \"0.1.1\", \"request_id\": \"...\"}"
}
```

**Check CloudWatch Logs:**
```bash
aws logs tail /aws/lambda/coinbot --follow --region eu-central-1
```

### Local Testing with Lambda Runtime Emulator

Test the container locally before deploying:

```bash
# Build for local testing (amd64 for Mac/Linux)
docker buildx build --platform linux/amd64 --provenance=false -t coinbot:test .

# Run with Lambda emulator
docker run --platform linux/amd64 -p 9000:8080 \
  -e BOT_ENABLED=true \
  -e BOT_DRY_RUN=true \
  -e BOT_DRY_RUN_INITIAL_BALANCE=1000 \
  -e BITVAVO_API_KEY=your-key \
  -e BITVAVO_API_SECRET=your-secret \
  -e S3_BUCKET_NAME=your-bucket \
  coinbot:test

# Test invocation (in another terminal)
curl "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'
```

### Monitoring

- **CloudWatch Logs**: `/aws/lambda/coinbot`
- **S3 Run Folders**: `s3://your-bucket/runs/YYYYMMDD_HHMM/`
  - Application logs: `s3://your-bucket/runs/YYYYMMDD_HHMM/logs.txt`
  - Technical analysis charts: `s3://your-bucket/runs/YYYYMMDD_HHMM/[H|S|B|X]_SYMBOL.png`
- **S3 Positions**: `s3://your-bucket/positions.json`
- **S3 Trades**: `s3://your-bucket/trades.json`

### Common Issues and Solutions

**Permission denied errors:**
- Solution: Ensure `chmod -R 755 ${LAMBDA_TASK_ROOT}` is in Dockerfile

**Package metadata not found:**
- Solution: Use hardcoded `__version__` instead of `importlib.metadata.version()`

**Shell redirection creating files:**
- Solution: Quote all package specs in pip install (e.g., `"pydantic>=2.0.0"`)

**OCI image format not supported:**
- Solution: Use `--provenance=false --sbom=false` flags when building

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
