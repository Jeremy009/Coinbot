"""AWS Lambda handler for the Coinbot trading bot."""

import json
import logging
import traceback
from typing import Any

from coinbot_backend import __version__
from coinbot_backend.config import settings


# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler function.

    Args:
        event: Lambda event data (unused, bot runs independently)
        context: Lambda context object

    Returns:
        Response dict with status and message
    """
    logger.info("Lambda function invoked")
    logger.info(f"Event: {json.dumps(event)}")

    # Get request ID (attribute name differs between real Lambda and emulator)
    request_id = getattr(context, 'request_id', None) or getattr(context, 'aws_request_id', 'local-test')
    logger.info(f"Request ID: {request_id}")

    try:
        # Import here to catch import errors
        from coinbot_backend.main import main

        logger.info("Starting bot iteration...")

        # Run one iteration of the bot
        main()

        logger.info(f"Bot iteration completed successfully using coinbot V{__version__}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Bot iteration completed successfully",
                "version": __version__,
                "request_id": request_id
            })
        }

    except Exception as e:
        error_msg = f"Bot iteration failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())

        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": error_msg,
                "error_type": type(e).__name__,
                "version": __version__,
                "request_id": request_id
            })
        }

    finally:
        # Ensure all log handlers flush their buffers to S3 before Lambda terminates
        # Without this, buffered logs in S3LogHandler will be lost
        logging.shutdown()