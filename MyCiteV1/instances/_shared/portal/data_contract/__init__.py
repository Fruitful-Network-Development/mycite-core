"""Shared data contract helpers for JSON-backed prototype storage."""

from .anthology_save_state import (
    SAVE_STATE_ENCODING,
    SAVE_STATE_SCHEMA,
    compact_payload_to_rows,
    compact_payload_to_save_state,
    rows_to_compact_payload,
    rows_to_save_state,
    save_state_to_compact_payload,
    save_state_to_rows,
)
