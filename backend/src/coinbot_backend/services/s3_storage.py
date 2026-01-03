"""S3 storage service for persisting bot data."""

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from coinbot_backend.config import settings

logger = logging.getLogger(__name__)


class S3StorageService:
    """Service for storing and retrieving bot data from S3."""

    def __init__(self) -> None:
        """Initialize S3 client."""
        # Always use AWS credential chain (AWS CLI, env vars, IAM role, etc.)
        # This automatically handles temporary credentials (session tokens) from IAM roles
        # Do NOT pass explicit credentials - it breaks Lambda's IAM role credentials
        self.s3_client = boto3.client("s3", region_name=settings.aws_region)
        self.bucket_name = settings.s3_bucket_name

    def upload_json(self, key: str, data: dict[str, Any] | list[Any]) -> bool:
        """
        Upload JSON data to S3.

        Args:
            key: S3 object key (filename)
            data: Dictionary or list to serialize as JSON

        Returns:
            True if successful, False otherwise
        """
        try:
            json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
            size_kb = len(json_bytes) / 1024
            logger.info(f"Uploading to S3: s3://{self.bucket_name}/{key} ({size_kb:.1f} KB)")

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json_bytes,
                ContentType="application/json",
            )
            logger.info(f"Successfully uploaded {key} to S3")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {key} to S3: {e}")
            return False

    def download_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        """
        Download JSON data from S3.

        Args:
            key: S3 object key (filename)

        Returns:
            Parsed JSON data (dict or list), or None if file doesn't exist or error occurs
        """
        try:
            logger.info(f"Downloading from S3: s3://{self.bucket_name}/{key}")
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            json_bytes = response["Body"].read()
            size_kb = len(json_bytes) / 1024
            data = json.loads(json_bytes.decode("utf-8"))
            logger.info(f"Successfully downloaded {key} from S3 ({size_kb:.1f} KB)")
            return data
        except self.s3_client.exceptions.NoSuchKey:
            logger.info(f"File {key} does not exist in S3 bucket {self.bucket_name}")
            return None
        except ClientError as e:
            logger.error(f"Failed to download {key} from S3: {e}")
            return None

    def upload_text(self, key: str, text: str) -> bool:
        """
        Upload text data to S3.

        Args:
            key: S3 object key (filename)
            text: Text content to upload

        Returns:
            True if successful, False otherwise
        """
        try:
            text_bytes = text.encode("utf-8")
            size_kb = len(text_bytes) / 1024

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=text_bytes,
                ContentType="text/plain",
            )
            logger.debug(f"Uploaded {key} to S3 ({size_kb:.1f} KB)")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {key} to S3: {e}")
            return False

    def upload_chart(self, key: str, chart_bytes: bytes) -> bool:
        """
        Upload chart image bytes to S3.

        Args:
            key: S3 object key (filename, should end with .png)
            chart_bytes: PNG image bytes

        Returns:
            True if successful, False otherwise
        """
        try:
            size_kb = len(chart_bytes) / 1024

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=chart_bytes,
                ContentType="image/png",
            )
            logger.debug(f"Uploaded chart {key} to S3 ({size_kb:.1f} KB)")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload chart {key} to S3: {e}")
            return False

    def append_text(self, key: str, text: str) -> bool:
        """
        Append text to an existing S3 file (downloads, appends, re-uploads).

        Args:
            key: S3 object key (filename)
            text: Text to append

        Returns:
            True if successful, False otherwise
        """
        try:
            # Download existing content
            existing_text = ""
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
                existing_text = response["Body"].read().decode("utf-8")
            except self.s3_client.exceptions.NoSuchKey:
                # File doesn't exist yet, that's fine
                pass

            # Append new text
            new_text = existing_text + text

            # Upload back
            return self.upload_text(key, new_text)
        except Exception as e:
            logger.error(f"Failed to append to {key} in S3: {e}")
            return False

    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            key: S3 object key (filename)

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False


class S3LogHandler(logging.Handler):
    """
    Custom logging handler that batches logs and uploads them to S3.

    Logs are buffered in memory and flushed to S3 when:
    - Buffer reaches max size
    - Handler is closed (end of program)
    - Manual flush is called
    """

    def __init__(
        self,
        s3_storage: S3StorageService,
        log_key: str,
        max_buffer_size: int = 100,
    ):
        """
        Initialize S3 log handler.

        Args:
            s3_storage: S3 storage service instance
            log_key: S3 key for the log file
            max_buffer_size: Number of log records to buffer before flushing
        """
        super().__init__()
        self.s3_storage = s3_storage
        self.log_key = log_key
        self.max_buffer_size = max_buffer_size
        self.buffer: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record (add to buffer)."""
        try:
            msg = self.format(record)
            self.buffer.append(msg + "\n")

            # Flush if buffer is full
            if len(self.buffer) >= self.max_buffer_size:
                self.flush()
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        """Flush buffered logs to S3."""
        if not self.buffer:
            return

        try:
            # Join all buffered logs
            log_content = "".join(self.buffer)

            # Upload to S3 (append mode)
            self.s3_storage.append_text(self.log_key, log_content)

            # Clear buffer
            self.buffer = []

        except Exception as e:
            # Don't use logger here to avoid infinite recursion
            print(f"Failed to flush logs to S3: {e}")

    def close(self) -> None:
        """Close handler and flush remaining logs."""
        self.flush()
        super().close()


# Singleton instance
_s3_storage: S3StorageService | None = None


def get_s3_storage() -> S3StorageService:
    """Get or create the singleton S3 storage service instance."""
    global _s3_storage
    if _s3_storage is None:
        _s3_storage = S3StorageService()
    return _s3_storage
