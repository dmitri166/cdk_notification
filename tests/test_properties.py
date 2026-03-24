# Feature: event-driven-notification-system, Property 1
# Feature: event-driven-notification-system, Property 3
"""
Property-based tests for the Event-Driven Notification System.

Validates: Requirements 2.1, 2.3, 2.4, 8.1, 8.2, 8.3
"""
from __future__ import annotations

import json
import sys
import os

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Ensure the project root is on the path so shared/ is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.schema import validate_payload, serialize_payload, deserialize_payload

# ---------------------------------------------------------------------------
# Generators / strategies
# ---------------------------------------------------------------------------

# A non-empty text string (printable, no surrogates) suitable for payload fields.
_nonempty_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=200,
)

# Valid ISO-8601 datetime strings.
_valid_timestamp = st.datetimes(
    min_value=__import__("datetime").datetime(2000, 1, 1),
    max_value=__import__("datetime").datetime(2099, 12, 31),
).map(lambda dt: dt.isoformat())

# Strategy that builds a fully valid Payload dict.
_valid_payload = st.fixed_dictionaries(
    {
        "event_id": _nonempty_text,
        "type": _nonempty_text,
        "message": _nonempty_text,
        "timestamp": _valid_timestamp,
    }
)

REQUIRED_FIELDS = ("event_id", "type", "message", "timestamp")


# ---------------------------------------------------------------------------
# Property 1 — Payload Validation Accepts Valid and Rejects Invalid Inputs
# Validates: Requirements 2.1, 2.3, 2.4, 8.1
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(_valid_payload)
def test_validator_accepts_valid_payloads(payload):
    """Property 1 (valid branch): validator must accept every well-formed payload."""
    # Feature: event-driven-notification-system, Property 1
    ok, err = validate_payload(payload)
    assert ok is True, f"Expected valid payload to be accepted, got error: {err}"
    assert err is None


@settings(max_examples=100)
@given(
    base=_valid_payload,
    missing_field=st.sampled_from(REQUIRED_FIELDS),
)
def test_validator_rejects_missing_field(base, missing_field):
    """Property 1 (missing field): validator must reject payloads with any required field absent."""
    # Feature: event-driven-notification-system, Property 1
    payload = {k: v for k, v in base.items() if k != missing_field}
    ok, err = validate_payload(payload)
    assert ok is False, "Expected missing-field payload to be rejected"
    assert err is not None
    assert err.get("field") == missing_field


@settings(max_examples=100)
@given(
    base=_valid_payload,
    bad_field=st.sampled_from(REQUIRED_FIELDS),
    bad_value=st.one_of(
        st.integers(),
        st.floats(allow_nan=False),
        st.booleans(),
        st.none(),
        st.lists(st.text()),
    ),
)
def test_validator_rejects_non_string_field(base, bad_field, bad_value):
    """Property 1 (wrong type): validator must reject payloads where a required field is not a string."""
    # Feature: event-driven-notification-system, Property 1
    payload = dict(base)
    payload[bad_field] = bad_value
    ok, err = validate_payload(payload)
    assert ok is False, f"Expected non-string field '{bad_field}' to be rejected"
    assert err is not None


@settings(max_examples=100)
@given(base=_valid_payload)
def test_validator_rejects_malformed_timestamp(base):
    """Property 1 (bad timestamp): validator must reject payloads with a non-ISO-8601 timestamp."""
    # Feature: event-driven-notification-system, Property 1
    payload = dict(base)
    payload["timestamp"] = "not-a-timestamp"
    ok, err = validate_payload(payload)
    assert ok is False, "Expected malformed timestamp to be rejected"
    assert err is not None
    assert err.get("field") == "timestamp"


@settings(max_examples=100)
@given(
    base=_valid_payload,
    empty_field=st.sampled_from(REQUIRED_FIELDS),
)
def test_validator_rejects_empty_string_field(base, empty_field):
    """Property 1 (empty string): validator must reject payloads where a required field is an empty string."""
    # Feature: event-driven-notification-system, Property 1
    payload = dict(base)
    payload[empty_field] = ""
    ok, err = validate_payload(payload)
    assert ok is False, f"Expected empty field '{empty_field}' to be rejected"
    assert err is not None


# ---------------------------------------------------------------------------
# Property 3 — Payload Serialization Round-Trip
# Validates: Requirements 8.2, 8.3
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(_valid_payload)
def test_payload_round_trip(payload):
    """Property 3: serialize→deserialize must yield an object equal to the original.

    Feature: event-driven-notification-system, Property 3
    Validates: Requirements 8.2, 8.3
    """
    serialized = serialize_payload(payload)
    assert isinstance(serialized, str), "serialize_payload must return a string"

    deserialized = deserialize_payload(serialized)
    assert deserialized == payload, (
        f"Round-trip failed: original={payload!r}, recovered={deserialized!r}"
    )


@settings(max_examples=100)
@given(_valid_payload)
def test_payload_round_trip_via_stdlib(payload):
    """Property 3 (stdlib): json.loads(json.dumps(payload)) == payload for all valid payloads.

    Feature: event-driven-notification-system, Property 3
    Validates: Requirements 8.2, 8.3
    """
    assert json.loads(json.dumps(payload)) == payload
