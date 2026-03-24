"""
Notification Dispatcher for the Consumer Lambda.

Provides dispatch_email and dispatch_telegram functions that send notifications
via AWS SES and Telegram Bot API respectively. Each function returns a Result without raising.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import boto3
import requests


@dataclass
class Result:
    success: bool
    error: str | None = None


def dispatch_email(payload: dict) -> Result:
    """Send an email via AWS SES only when payload["type"] == "deployment".

    For any other type, returns success without calling SES.
    Retrieves the recipient address from SES_RECIPIENT_EMAIL env var.
    """
    if payload.get("type") != "deployment":
        return Result(success=True)

    recipient = os.environ["SES_RECIPIENT_EMAIL"]

    try:
        ses_client = boto3.client("ses")
        ses_client.send_email(
            Source=recipient,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {
                    "Data": f"Deployment notification: {payload.get('event_id', '')}",
                },
                "Body": {
                    "Text": {
                        "Data": payload.get("message", ""),
                    },
                },
            },
        )
        return Result(success=True)
    except Exception as exc:  # noqa: BLE001
        return Result(success=False, error=str(exc))


def dispatch_telegram(payload: dict) -> Result:
    """Send a Telegram message for all message types.

    Retrieves credentials from environment variables:
      TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    text = f"[{payload.get('type', 'unknown')}] {payload.get('message', '')}"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        resp.raise_for_status()
        return Result(success=True)
    except Exception as exc:  # noqa: BLE001
        return Result(success=False, error=str(exc))
