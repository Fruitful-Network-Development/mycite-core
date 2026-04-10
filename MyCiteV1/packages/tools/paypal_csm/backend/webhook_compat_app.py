from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, g, jsonify, request

app = Flask(__name__)
log = logging.getLogger("paypal_webhook_compat")
logging.basicConfig(level=str(os.getenv("PAYPAL_PROXY_LOG_LEVEL", "INFO")).upper())

STATE_DIR = Path(os.getenv("PAYPAL_PROXY_STATE_DIR", "/state"))
ACTIONS_LOG = STATE_DIR / "actions.ndjson"


def _request_id() -> str:
    current = getattr(g, "request_id", "")
    if current:
        return str(current)
    rid = (request.headers.get("X-Request-Id", "") or "").strip() or uuid.uuid4().hex
    g.request_id = rid
    return rid


def _append_ndjson(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")


def _append_action(event_type: str, payload: dict[str, Any]) -> None:
    event = dict(payload)
    event["type"] = event_type
    event["ts_unix_ms"] = int(time.time() * 1000)
    _append_ndjson(ACTIONS_LOG, event)
    log.info("%s %s", event_type, json.dumps(event, sort_keys=True))


@app.after_request
def _audit(response):
    response.headers["X-Request-Id"] = _request_id()
    return response


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "ok": True,
            "service": "paypal_webhook_compat",
            "mode": "webhook_compat",
        }
    )


@app.post("/paypal/webhook")
def paypal_webhook():
    body = request.get_json(silent=True)
    event_type = ""
    event_id = ""
    if isinstance(body, dict):
        event_type = str(body.get("event_type") or "")
        event_id = str(body.get("id") or "")

    rid = _request_id()
    _append_action(
        "paypal.webhook.received",
        {
            "request_id": rid,
            "action": "POST /paypal/webhook",
            "event_type": event_type,
            "event_id": event_id,
            "content_type": str(request.headers.get("Content-Type") or ""),
            "content_length": int(request.content_length or 0),
            "status_code": 202,
        },
    )
    return jsonify({"ok": True, "status": "accepted", "request_id": rid, "event_type": event_type}), 202


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
