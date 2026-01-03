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

## Deployment

### AWS Lambda Deployment

The bot is designed to run on AWS Lambda with scheduled invocations.

#### Prerequisites

- AWS CLI configured with credentials
- ECR repository created: `coinbot`
- S3 bucket for storing bot data
- Bitvavo API credentials

#### Build and Deploy

1. **Build and push Docker image to ECR**:
```bash
# Authenticate to the AWS CLI
aws login

# Authenticate Docker to ECR
aws ecr get-login-password --region eu-central-1 | \
  docker login --username AWS --password-stdin 080328315628.dkr.ecr.eu-central-1.amazonaws.com

# Build for ARM64 (Lambda)
docker buildx build \                                                                                                        
  --platform linux/arm64 \
  --provenance=false \
  --sbom=false \
  -t 080328315628.dkr.ecr.eu-central-1.amazonaws.com/coinbot:latest \
  --push .

```

2. **Create or update Lambda function**:
```bash
# Create function (first time only)
aws lambda create-function \
  --function-name coinbot \
  --package-type Image \
  --code ImageUri=<account-id>.dkr.ecr.eu-central-1.amazonaws.com/coinbot:latest \
  --role arn:aws:iam::<account-id>:role/coinbot-lambda-role \
  --architectures arm64 \
  --memory-size 1024 \
  --timeout 900 \
  --region eu-central-1

# Update existing function
aws lambda update-function-code \
  --function-name coinbot \
  --image-uri 080328315628.dkr.ecr.eu-central-1.amazonaws.com/coinbot:latest \
  --region eu-central-1
```

3. **Configure environment variables** (via AWS Console or CLI):
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

4. **Test the function**:
```bash
aws lambda invoke --function-name coinbot --region eu-central-1 response.json
cat response.json
```

5. **Schedule with EventBridge** (optional - run every 2 hours):
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

#### Local Testing with Lambda Runtime

Test the container locally before deploying:

```bash
# Build for local testing (amd64)
docker buildx build --platform linux/amd64 --provenance=false -t coinbot:test .

# Run with Lambda emulator
docker run --platform linux/amd64 -p 9000:8080 \
  -e BOT_ENABLED=true \
  -e BOT_DRY_RUN=true \
  -e BITVAVO_API_KEY=your-key \
  -e BITVAVO_API_SECRET=your-secret \
  -e S3_BUCKET_NAME=your-bucket \
  coinbot:test

# Test invocation (in another terminal)
curl "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'
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
