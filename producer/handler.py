"""
Producer Lambda handler for the Event-Driven Notification System.

Validates the incoming payload, publishes it to SQS, and returns a
structured response. Every invocation result is logged to CloudWatch.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import boto3

from schema import serialize_payload, validate_payload

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_sqs_client = None


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def _log(level: str, event_id: str | None, status: str, **extra) -> None:
    """Emit a structured CloudWatch log entry."""
    entry = {
        "level": level,
        "lambda": "producer",
        "event_id": event_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    entry.update(extra)
    log_fn = logger.error if level == "ERROR" else logger.info
    log_fn(json.dumps(entry))


def handler(event: dict, context: object) -> dict:
    """Lambda entry point.

    Parameters
    ----------
    event:
        The raw Lambda invocation payload (expected to be the Payload dict).
    context:
        The Lambda context object (unused).

    Returns
    -------
    dict
        ``{ statusCode: 200, body: { messageId } }`` on success, or
        ``{ statusCode: 400, body: { error, field } }`` on validation failure.
    """
    is_valid, error_detail = validate_payload(event)

    if not is_valid:
        error = error_detail.get("error", "Validation error")
        field = error_detail.get("field")
        event_id = event.get("event_id") if isinstance(event, dict) else None

        _log("ERROR", event_id, "failure", error=error, field=field)

        return {
            "statusCode": 400,
            "body": {"error": error, "field": field},
        }

    event_id: str = event["event_id"]
    queue_url: str = os.environ["SQS_QUEUE_URL"]

    sqs = _get_sqs_client()
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=serialize_payload(event),  # type: ignore[arg-type]
    )
    message_id: str = response["MessageId"]

    _log("INFO", event_id, "success", channel="sqs", messageId=message_id)

    return {
        "statusCode": 200,
        "body": {"messageId": message_id},
    }
