"""Unit tests for the PayPal webhook auto-provisioning helpers.

PayPal HTTP calls are patched at the urllib boundary (or at the sibling
helpers) so the suite stays offline.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import (
    _create_paypal_webhook,
    _find_or_create_paypal_webhook,
    _list_paypal_webhooks,
    _PaypalWebhookError,
)

APP = "MyCiteV2.instances._shared.portal_host.app"
BASE = "https://api-m.sandbox.paypal.com"
URL = "https://example.test/__fnd/paypal/webhook"


class _FakeResp:
    """Minimal context-manager response with ``.read()`` for urlopen patches."""

    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *_a: object) -> bool:
        return False


class ListWebhooksTests(unittest.TestCase):
    def test_parses_webhooks_array(self) -> None:
        with patch("urllib.request.urlopen", return_value=_FakeResp({"webhooks": [{"id": "W1", "url": URL}]})):
            hooks = _list_paypal_webhooks(access_token="t", base_url=BASE)
        self.assertEqual(hooks, [{"id": "W1", "url": URL}])

    def test_returns_empty_on_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("boom")):
            self.assertEqual(_list_paypal_webhooks(access_token="t", base_url=BASE), [])

    def test_returns_empty_when_key_missing(self) -> None:
        with patch("urllib.request.urlopen", return_value=_FakeResp({})):
            self.assertEqual(_list_paypal_webhooks(access_token="t", base_url=BASE), [])


class CreateWebhookTests(unittest.TestCase):
    def test_posts_event_types_as_objects(self) -> None:
        captured: dict = {}

        def fake_urlopen(req, timeout=0):
            captured["body"] = json.loads(req.data.decode())
            return _FakeResp({"id": "W9", "url": URL})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            out = _create_paypal_webhook(access_token="t", base_url=BASE, url=URL, event_types=("A", "B"))
        self.assertEqual(out["id"], "W9")
        self.assertEqual(captured["body"]["url"], URL)
        # The gotcha: event_types must be a list of {"name": ...} objects.
        self.assertEqual(captured["body"]["event_types"], [{"name": "A"}, {"name": "B"}])

    def test_http_error_raises_named(self) -> None:
        err = urllib.error.HTTPError(
            URL, 422, "Unprocessable", None,
            io.BytesIO(b'{"name":"WEBHOOK_URL_ALREADY_EXISTS"}'),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(_PaypalWebhookError) as ctx:
                _create_paypal_webhook(access_token="t", base_url=BASE, url=URL, event_types=("A",))
        self.assertEqual(ctx.exception.name, "WEBHOOK_URL_ALREADY_EXISTS")


class FindOrCreateTests(unittest.TestCase):
    def test_reuses_existing_match_no_create(self) -> None:
        # Existing URL has a trailing slash — match must be slash-tolerant.
        with patch(f"{APP}._list_paypal_webhooks", return_value=[{"id": "W1", "url": URL + "/"}]), patch(
            f"{APP}._create_paypal_webhook"
        ) as create:
            wid, _ = _find_or_create_paypal_webhook(
                access_token="t", base_url=BASE, url=URL, event_types=("A",)
            )
        self.assertEqual(wid, "W1")
        create.assert_not_called()

    def test_creates_when_no_match(self) -> None:
        with patch(f"{APP}._list_paypal_webhooks", return_value=[]), patch(
            f"{APP}._create_paypal_webhook", return_value={"id": "W2", "url": URL}
        ) as create:
            wid, _ = _find_or_create_paypal_webhook(
                access_token="t", base_url=BASE, url=URL, event_types=("A",)
            )
        self.assertEqual(wid, "W2")
        create.assert_called_once()

    def test_already_exists_then_relists(self) -> None:
        # First list empty → create raises ALREADY_EXISTS (list lagged) →
        # re-list now sees it and we return the match.
        lists = [[], [{"id": "W3", "url": URL}]]
        with patch(f"{APP}._list_paypal_webhooks", side_effect=lambda **_k: lists.pop(0)), patch(
            f"{APP}._create_paypal_webhook",
            side_effect=_PaypalWebhookError("WEBHOOK_URL_ALREADY_EXISTS"),
        ):
            wid, _ = _find_or_create_paypal_webhook(
                access_token="t", base_url=BASE, url=URL, event_types=("A",)
            )
        self.assertEqual(wid, "W3")


if __name__ == "__main__":
    unittest.main()
