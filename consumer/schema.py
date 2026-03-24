"""
Shared Payload schema definition and validation for the Event-Driven Notification System.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import TypedDict


class Payload(TypedDict):
    event_id: str
    type: str
    message: str
    timestamp: str


REQUIRED_FIELDS: tuple[str, ...] = ("event_id", "type", "message", "timestamp")


def _is_valid_iso8601(value: str) -> bool:
    """Return True if *value* is a valid ISO-8601 datetime string."""
    if not isinstance(value, str):
        return False
    # Try common ISO-8601 formats accepted by datetime.fromisoformat (Python 3.7+).
    # Python 3.11+ fromisoformat handles the full spec; for 3.12 this is sufficient.
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        pass
    # Also accept the 'Z' suffix (UTC) which Python < 3.11 fromisoformat rejects.
    if value.endswith("Z"):
        try:
            datetime.fromisoformat(value[:-1] + "+00:00")
            return True
        except ValueError:
            pass
    return False


def validate_payload(data: object) -> tuple[bool, dict | None]:
    """Validate *data* against the Payload schema.

    Returns:
        (True, None)                        – payload is valid
        (False, {"error": ..., "field": ...}) – payload is invalid; statusCode 400
    """
    if not isinstance(data, dict):
        return False, {"error": "Payload must be a JSON object", "field": None}

    for field in REQUIRED_FIELDS:
        if field not in data:
            return False, {"error": f"Missing field: {field}", "field": field}
        if not isinstance(data[field], str):
            return False, {
                "error": f"Field '{field}' must be a string",
                "field": field,
            }
        if data[field] == "":
            return False, {
                "error": f"Field '{field}' must not be empty",
                "field": field,
            }

    if not _is_valid_iso8601(data["timestamp"]):
        return False, {
            "error": "Invalid timestamp format; expected ISO-8601",
            "field": "timestamp",
        }

    return True, None


def serialize_payload(payload: Payload) -> str:
    """Serialize a Payload dict to a JSON string."""
    return json.dumps(payload)


def deserialize_payload(body: str) -> Payload:
    """Deserialize a JSON string to a Payload dict (no validation)."""
    return json.loads(body)
