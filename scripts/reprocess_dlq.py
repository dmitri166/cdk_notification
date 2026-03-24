#!/usr/bin/env python3
"""
DLQ Reprocessing Script

Reads messages from the Dead Letter Queue and republishes them to the main SQS queue.
A message is only deleted from the DLQ after a successful republish.

Environment variables:
    DLQ_URL       - URL of the Dead Letter Queue
    SQS_QUEUE_URL - URL of the main SQS queue
"""

import json
import logging
import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

MAX_MESSAGES_PER_POLL = 10  # SQS maximum per ReceiveMessage call
WAIT_TIME_SECONDS = 1


def get_event_id(body: str) -> str:
    """Parse event_id from message body JSON. Returns '<unknown>' on any error."""
    try:
        data = json.loads(body)
        return str(data.get("event_id", "<unknown>"))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return "<unknown>"


def reprocess_dlq(sqs_client, dlq_url: str, queue_url: str) -> int:
    """
    Poll the DLQ until empty, republishing each message to queue_url.

    Returns the total number of successfully reprocessed messages.
    """
    total_reprocessed = 0

    while True:
        response = sqs_client.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=MAX_MESSAGES_PER_POLL,
            WaitTimeSeconds=WAIT_TIME_SECONDS,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        if not messages:
            logger.info("No more messages in DLQ. Reprocessing complete.")
            break

        for msg in messages:
            receipt_handle = msg["ReceiptHandle"]
            body = msg.get("Body", "")
            event_id = get_event_id(body)

            # Attempt to republish to the main queue
            try:
                sqs_client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=body,
                )
            except (BotoCoreError, ClientError) as exc:
                logger.error(
                    "Failed to republish message event_id=%s to queue — leaving in DLQ. Error: %s",
                    event_id,
                    exc,
                )
                continue  # Do NOT delete from DLQ

            # Only delete from DLQ after a confirmed successful send
            try:
                sqs_client.delete_message(
                    QueueUrl=dlq_url,
                    ReceiptHandle=receipt_handle,
                )
            except (BotoCoreError, ClientError) as exc:
                logger.warning(
                    "Message event_id=%s was republished but could not be deleted from DLQ. "
                    "It may be reprocessed again. Error: %s",
                    event_id,
                    exc,
                )
                continue

            total_reprocessed += 1
            logger.info(
                "Reprocessed message event_id=%s status=success",
                event_id,
            )

    return total_reprocessed


def main() -> None:
    dlq_url = os.environ.get("DLQ_URL")
    queue_url = os.environ.get("SQS_QUEUE_URL")

    if not dlq_url:
        logger.error("Environment variable DLQ_URL is not set.")
        sys.exit(1)
    if not queue_url:
        logger.error("Environment variable SQS_QUEUE_URL is not set.")
        sys.exit(1)

    sqs_client = boto3.client("sqs")

    logger.info("Starting DLQ reprocessing. DLQ=%s Target=%s", dlq_url, queue_url)
    total = reprocess_dlq(sqs_client, dlq_url, queue_url)
    logger.info("DLQ reprocessing finished. total_reprocessed=%d", total)


if __name__ == "__main__":
    main()
