# Coinbot Trading Bot - AWS Lambda Dockerfile
# Uses AWS Lambda Python 3.12 base image

FROM public.ecr.aws/lambda/python:3.12

# Install dependencies first (before copying source code)
RUN pip install --no-cache-dir \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.1.0" \
    "python-dotenv>=1.0.0" \
    "python-bitvavo-api>=1.2.2" \
    "pandas>=2.0.0" \
    "numpy>=1.24.0" \
    "tqdm>=4.66.0" \
    "matplotlib>=3.7.0" \
    "boto3>=1.34.0" \
    "botocore[crt]>=1.34.0"

# Copy backend source code to ${LAMBDA_TASK_ROOT}
COPY backend/src/coinbot_backend ${LAMBDA_TASK_ROOT}/coinbot_backend
COPY backend/lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Fix file permissions for Lambda runtime
RUN chmod -R 755 ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (function name in lambda_handler.py)
CMD ["lambda_handler.handler"]
