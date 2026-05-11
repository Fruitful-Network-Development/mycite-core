"""SQLite-backed newsletter contact log and profile adapter.

Implements AwsCsmNewsletterStatePort against a SQLite database. Each domain's
contact log and newsletter profile is stored as a JSON document keyed by domain.
Tables are created on first connection (safe to reuse an existing authority DB).

This adapter is the MOS-SQL replacement for FilesystemAwsCsmNewsletterStateAdapter
for contact log and profile I/O. Methods that require AWS CSM tool profile reads
(list_verified_author_profiles, ensure_domain_bootstrap) and secret access
(runtime_secret_seed) are not implemented — they raise NotImplementedError.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from MyCiteV2.packages.ports.aws_csm_newsletter import (
    AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
    AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
    AwsCsmNewsletterStatePort,
)

_NEWSLETTER_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS newsletter_contact_logs (
    domain       TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS newsletter_profiles (
    domain       TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL DEFAULT 0
);
"""


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


class SqliteMosAwsCsmNewsletterStateAdapter:
    """SQLite-backed implementation of AwsCsmNewsletterStatePort.

    Stores newsletter contact logs and profiles as JSON documents in a SQLite
    database. Suitable for production use after filesystem contact log migration.

    Not implemented: list_verified_author_profiles, ensure_domain_bootstrap,
    runtime_secret_seed (these depend on AWS CSM tool profile infrastructure
    that remains filesystem-based until a separate migration task).
    """

    def __init__(
        self,
        db_file: str | Path,
        *,
        clock: Any = None,
    ) -> None:
        self._db_file = Path(db_file)
        self._clock = clock or (lambda: int(time.time() * 1000))

    def _connect(self) -> sqlite3.Connection:
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(_NEWSLETTER_TABLES_SQL)
        return conn

    # ------------------------------------------------------------------
    # Contact log
    # ------------------------------------------------------------------

    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        token = _normalized_domain(domain)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM newsletter_contact_logs WHERE domain = ?",
                (token,),
            ).fetchone()
        if row is None:
            return {}
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        if _as_text(payload.get("schema")) != AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA:
            return {}
        return dict(payload)

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = _normalized_domain(domain)
        body = dict(payload if isinstance(payload, dict) else {})
        body["schema"] = AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA
        body["domain"] = token
        body["contacts"] = list(body.get("contacts") or [])
        body["dispatches"] = list(body.get("dispatches") or [])[-20:]
        now_ms = self._clock()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO newsletter_contact_logs (domain, payload_json, updated_at_unix_ms)
                VALUES (?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at_unix_ms = excluded.updated_at_unix_ms
                """,
                (token, json.dumps(body, separators=(",", ":"), sort_keys=True), now_ms),
            )
            conn.commit()
        return body

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def load_profile(self, *, domain: str) -> dict[str, Any]:
        token = _normalized_domain(domain)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM newsletter_profiles WHERE domain = ?",
                (token,),
            ).fetchone()
        if row is None:
            return {}
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        if _as_text(payload.get("schema")) != AWS_CSM_NEWSLETTER_PROFILE_SCHEMA:
            return {}
        return dict(payload)

    def save_profile(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = _normalized_domain(domain)
        body = dict(payload if isinstance(payload, dict) else {})
        body["schema"] = AWS_CSM_NEWSLETTER_PROFILE_SCHEMA
        body["domain"] = token
        now_ms = self._clock()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO newsletter_profiles (domain, payload_json, updated_at_unix_ms)
                VALUES (?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at_unix_ms = excluded.updated_at_unix_ms
                """,
                (token, json.dumps(body, separators=(",", ":"), sort_keys=True), now_ms),
            )
            conn.commit()
        return body

    # ------------------------------------------------------------------
    # Domain listing
    # ------------------------------------------------------------------

    def list_newsletter_domains(self) -> list[str]:
        with self._connect() as conn:
            log_domains = {
                row[0] for row in conn.execute(
                    "SELECT domain FROM newsletter_contact_logs"
                ).fetchall()
            }
            profile_domains = {
                row[0] for row in conn.execute(
                    "SELECT domain FROM newsletter_profiles"
                ).fetchall()
            }
        return sorted(log_domains | profile_domains)

    # ------------------------------------------------------------------
    # Not implemented — require filesystem/AWS CSM infrastructure
    # ------------------------------------------------------------------

    def list_verified_author_profiles(self, *, domain: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "list_verified_author_profiles requires filesystem AWS CSM tool profiles — "
            "use FilesystemAwsCsmNewsletterStateAdapter for this method"
        )

    def ensure_domain_bootstrap(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
        unsubscribe_secret_name: str,
        dispatch_callback_secret_name: str,
        inbound_callback_secret_name: str,
        inbound_processor_lambda_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raise NotImplementedError(
            "ensure_domain_bootstrap requires filesystem AWS CSM tool profiles — "
            "use FilesystemAwsCsmNewsletterStateAdapter for this method"
        )

    def runtime_secret_seed(self, *, secret_kind: str) -> str:
        raise NotImplementedError(
            "runtime_secret_seed requires filesystem runtime secrets — "
            "use FilesystemAwsCsmNewsletterStateAdapter for this method"
        )
