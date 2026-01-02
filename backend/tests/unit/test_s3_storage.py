"""Simple integration tests for S3 storage service."""

import logging
import uuid

from coinbot_backend.config import settings
from coinbot_backend.services.s3_storage import S3LogHandler, get_s3_storage


class TestS3StorageIntegration:
    """Simple S3 integration test."""

    def test_config(self):
        """Test that S3 configuration is properly set."""
        # Check settings are configured
        assert settings.s3_bucket_name is not None
        assert settings.s3_bucket_name != ""
        assert settings.aws_region is not None
        assert settings.aws_region != ""

        # Check storage service initializes correctly
        storage = get_s3_storage()
        assert storage.bucket_name is not None
        assert storage.bucket_name != ""
        assert storage.s3_client is not None

    def test_s3_upload_download_delete_cycle(self):
        """Test complete S3 lifecycle: upload, download, delete."""
        # Get S3 storage instance
        storage = get_s3_storage()
        test_key = "unit_test.json"

        # 1. Assert file doesn't exist (fail if it does - test should clean up after itself)
        assert storage.file_exists(test_key) is False, (
            f"Test file {test_key} already exists in S3! "
            "Previous test run did not clean up properly."
        )

        # 2. Create test data with UUID
        test_uuid = str(uuid.uuid4())
        test_data = {"test_id": test_uuid}

        # 3. Upload to S3
        upload_success = storage.upload_json(test_key, test_data)
        assert upload_success is True

        # 4. Check file exists
        assert storage.file_exists(test_key) is True

        # 5. Download from S3
        downloaded_data = storage.download_json(test_key)
        assert downloaded_data is not None

        # 6. Verify contents match
        assert downloaded_data == test_data
        assert downloaded_data["test_id"] == test_uuid

        # 7. Delete from S3
        storage.s3_client.delete_object(Bucket=storage.bucket_name, Key=test_key)

        # 8. Assert file is gone
        assert storage.file_exists(test_key) is False

        # 9. Verify download returns None for non-existent file
        deleted_data = storage.download_json(test_key)
        assert deleted_data is None

    def test_upload_text_cycle(self):
        """Test text upload, download, and delete lifecycle."""
        storage = get_s3_storage()
        test_key = "unit_test.txt"

        # 1. Assert file doesn't exist
        assert storage.file_exists(test_key) is False, (
            f"Test file {test_key} already exists in S3! "
            "Previous test run did not clean up properly."
        )

        # 2. Create test text with UUID
        test_uuid = str(uuid.uuid4())
        test_text = f"Test log entry: {test_uuid}\n"

        # 3. Upload text to S3
        upload_success = storage.upload_text(test_key, test_text)
        assert upload_success is True

        # 4. Check file exists
        assert storage.file_exists(test_key) is True

        # 5. Download and verify (using S3 client directly since there's no download_text method)
        response = storage.s3_client.get_object(Bucket=storage.bucket_name, Key=test_key)
        downloaded_text = response["Body"].read().decode("utf-8")
        assert downloaded_text == test_text
        assert test_uuid in downloaded_text

        # 6. Delete from S3
        storage.s3_client.delete_object(Bucket=storage.bucket_name, Key=test_key)

        # 7. Assert file is gone
        assert storage.file_exists(test_key) is False

    def test_append_text_cycle(self):
        """Test text append functionality and delete lifecycle."""
        storage = get_s3_storage()
        test_key = "unit_test_append.log"

        # 1. Assert file doesn't exist
        assert storage.file_exists(test_key) is False, (
            f"Test file {test_key} already exists in S3! "
            "Previous test run did not clean up properly."
        )

        # 2. Create test UUIDs for multiple appends
        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        uuid3 = str(uuid.uuid4())

        # 3. Append first text (to non-existent file - should create it)
        line1 = f"Log entry 1: {uuid1}\n"
        append_success = storage.append_text(test_key, line1)
        assert append_success is True

        # 4. Check file exists
        assert storage.file_exists(test_key) is True

        # 5. Append second text
        line2 = f"Log entry 2: {uuid2}\n"
        append_success = storage.append_text(test_key, line2)
        assert append_success is True

        # 6. Append third text
        line3 = f"Log entry 3: {uuid3}\n"
        append_success = storage.append_text(test_key, line3)
        assert append_success is True

        # 7. Download and verify all lines are present in order
        response = storage.s3_client.get_object(Bucket=storage.bucket_name, Key=test_key)
        full_content = response["Body"].read().decode("utf-8")

        assert uuid1 in full_content
        assert uuid2 in full_content
        assert uuid3 in full_content
        assert full_content == line1 + line2 + line3
        assert full_content.count("\n") == 3

        # 8. Delete from S3
        storage.s3_client.delete_object(Bucket=storage.bucket_name, Key=test_key)

        # 9. Assert file is gone
        assert storage.file_exists(test_key) is False


class TestS3StorageErrorHandling:
    """Test S3 error handling when operations fail."""

    def test_upload_json_with_invalid_bucket(self):
        """Test upload_json returns False when bucket doesn't exist."""
        storage = get_s3_storage()

        # Temporarily use invalid bucket
        original_bucket = storage.bucket_name
        storage.bucket_name = "nonexistent-bucket-12345-xyz"

        test_data = {"test": "data"}
        result = storage.upload_json("test.json", test_data)

        # Should return False on error
        assert result is False

        # Restore original bucket
        storage.bucket_name = original_bucket

    def test_download_json_with_invalid_bucket(self):
        """Test download_json returns None when bucket doesn't exist."""
        storage = get_s3_storage()

        # Temporarily use invalid bucket
        original_bucket = storage.bucket_name
        storage.bucket_name = "nonexistent-bucket-12345-xyz"

        result = storage.download_json("test.json")

        # Should return None on error
        assert result is None

        # Restore original bucket
        storage.bucket_name = original_bucket

    def test_upload_text_with_invalid_bucket(self):
        """Test upload_text returns False when bucket doesn't exist."""
        storage = get_s3_storage()

        # Temporarily use invalid bucket
        original_bucket = storage.bucket_name
        storage.bucket_name = "nonexistent-bucket-12345-xyz"

        result = storage.upload_text("test.txt", "test content")

        # Should return False on error
        assert result is False

        # Restore original bucket
        storage.bucket_name = original_bucket

    def test_append_text_with_invalid_bucket(self):
        """Test append_text returns False when bucket doesn't exist."""
        storage = get_s3_storage()

        # Temporarily use invalid bucket
        original_bucket = storage.bucket_name
        storage.bucket_name = "nonexistent-bucket-12345-xyz"

        result = storage.append_text("test.log", "log line\n")

        # Should return False on error
        assert result is False

        # Restore original bucket
        storage.bucket_name = original_bucket


class TestS3LogHandler:
    """Test S3LogHandler for logging to S3."""

    def test_log_handler_buffers_and_flushes(self):
        """Test that log handler buffers messages and flushes to S3."""
        storage = get_s3_storage()
        test_key = "unit_test_handler.log"

        # Clean up if exists
        if storage.file_exists(test_key):
            storage.s3_client.delete_object(Bucket=storage.bucket_name, Key=test_key)

        # 1. Create log handler with small buffer size
        handler = S3LogHandler(
            s3_storage=storage, log_key=test_key, max_buffer_size=100
        )
        handler.setFormatter(logging.Formatter("%(message)s"))

        # 2. Emit some log records
        test_uuid = str(uuid.uuid4())
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"Test log message: {test_uuid}",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        # 3. Buffer should have the message (not yet flushed)
        assert len(handler.buffer) == 1
        assert test_uuid in handler.buffer[0]

        # 4. File should not exist yet (not flushed)
        assert storage.file_exists(test_key) is False

        # 5. Manually flush
        handler.flush()

        # 6. Buffer should be empty
        assert len(handler.buffer) == 0

        # 7. File should exist now
        assert storage.file_exists(test_key) is True

        # 8. Download and verify content
        response = storage.s3_client.get_object(Bucket=storage.bucket_name, Key=test_key)
        content = response["Body"].read().decode("utf-8")
        assert test_uuid in content

        # 9. Clean up
        handler.close()
        storage.s3_client.delete_object(Bucket=storage.bucket_name, Key=test_key)
        assert storage.file_exists(test_key) is False

    def test_log_handler_auto_flush_on_buffer_full(self):
        """Test that handler auto-flushes when buffer is full."""
        storage = get_s3_storage()
        test_key = "unit_test_auto_flush.log"

        # Clean up if exists
        if storage.file_exists(test_key):
            storage.s3_client.delete_object(Bucket=storage.bucket_name, Key=test_key)

        # 1. Create handler with buffer size of 3
        handler = S3LogHandler(s3_storage=storage, log_key=test_key, max_buffer_size=3)
        handler.setFormatter(logging.Formatter("%(message)s"))

        # 2. Create unique UUIDs
        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        uuid3 = str(uuid.uuid4())

        # 3. Emit 3 records (should trigger auto-flush)
        for msg_uuid in [uuid1, uuid2, uuid3]:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Log: {msg_uuid}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        # 4. Buffer should be empty (auto-flushed)
        assert len(handler.buffer) == 0

        # 5. File should exist
        assert storage.file_exists(test_key) is True

        # 6. Verify all messages are in S3
        response = storage.s3_client.get_object(Bucket=storage.bucket_name, Key=test_key)
        content = response["Body"].read().decode("utf-8")
        assert uuid1 in content
        assert uuid2 in content
        assert uuid3 in content

        # 7. Clean up
        handler.close()
        storage.s3_client.delete_object(Bucket=storage.bucket_name, Key=test_key)
        assert storage.file_exists(test_key) is False
