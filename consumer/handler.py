"""
Consumer Lambda handler — SQS batch processing entry point.

Iterates over SQS Records, validates each message body against the Payload
schema, dispatches email and WhatsApp notifications, and returns a partial-batch
response so SQS only retries failed records.

Idempotency is enforced via an in-memory set scoped to the current invocation.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from dispatcher import dispatch_email, dispatch_telegram
from schema import deserialize_payload, validate_payload

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process an SQS batch event.

    Returns:
        { "batchItemFailures": [{ "itemIdentifier": messageId }, ...] }
    """
    batch_item_failures: list[dict[str, str]] = []
    seen_event_ids: set[str] = set()

    for record in event.get("Records", []):
        message_id: str = record["messageId"]
        body: str = record.get("body", "")

        # ── Deserialize ──────────────────────────────────────────────────────
        try:
            data = deserialize_payload(body)
        except Exception as exc:
            logger.error(
                json.dumps({
                    "level": "ERROR",
                    "lambda": "consumer",
                    "event_id": None,
                    "status": "failure",
                    "error": f"Schema violation — failed to deserialize body: {exc}",
                    "messageId": message_id,
                })
            )
            batch_item_failures.append({"itemIdentifier": message_id})
            continue

        # ── Validate ─────────────────────────────────────────────────────────
        valid, error_detail = validate_payload(data)
        if not valid:
            logger.error(
                json.dumps({
                    "level": "ERROR",
                    "lambda": "consumer",
                    "event_id": data.get("event_id") if isinstance(data, dict) else None,
                    "status": "failure",
                    "error": f"Schema violation — {error_detail}",
                    "messageId": message_id,
                })
            )
            batch_item_failures.append({"itemIdentifier": message_id})
            continue

        event_id: str = data["event_id"]

        # ── Idempotency check ─────────────────────────────────────────────────
        if event_id in seen_event_ids:
            logger.info(
                json.dumps({
                    "level": "INFO",
                    "lambda": "consumer",
                    "event_id": event_id,
                    "status": "duplicate",
                    "messageId": message_id,
                })
            )
            continue

        seen_event_ids.add(event_id)

        # ── Dispatch ──────────────────────────────────────────────────────────
        record_failed = False

        # Email (SES) — only for type == "deployment"
        email_result = dispatch_email(data)
        if not email_result.success:
            logger.error(
                json.dumps({
                    "level": "ERROR",
                    "lambda": "consumer",
                    "event_id": event_id,
                    "channel": "ses",
                    "status": "failure",
                    "error": email_result.error,
                    "messageId": message_id,
                })
            )
            record_failed = True
        else:
            logger.info(
                json.dumps({
                    "level": "INFO",
                    "lambda": "consumer",
                    "event_id": event_id,
                    "channel": "ses",
                    "status": "success",
                    "messageId": message_id,
                })
            )

        # Telegram — all message types
        whatsapp_result = dispatch_telegram(data)
        if not whatsapp_result.success:
            logger.error(
                json.dumps({
                    "level": "ERROR",
                    "lambda": "consumer",
                    "event_id": event_id,
                    "channel": "telegram",
                    "status": "failure",
                    "error": whatsapp_result.error,
                    "messageId": message_id,
                })
            )
            record_failed = True
        else:
            logger.info(
                json.dumps({
                    "level": "INFO",
                    "lambda": "consumer",
                    "event_id": event_id,
                    "channel": "telegram",
                    "status": "success",
                    "messageId": message_id,
                })
            )

        if record_failed:
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}
