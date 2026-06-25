"""ext_paypal — webhook config + recent donation orders.

Prefers the MOS-backed orders + webhook datums (per Phase D.3 of the
unification audit). Falls back to the legacy filesystem NDJSON and
per-grantee JSON config when MOS data is missing.

Phase 8 (grantee_profile_contract.md): inline ``grantee.paypal.webhook_url``
is the canonical source. The MOS adapter and the legacy
``paypal-webhook.{msn_id}.json`` sidecar remain as fallbacks for one
transition cycle — production migration is the gate for retiring them.

Phase 14d.3: the payload now carries an ``export_action`` link that
points at ``GET /__fnd/paypal/admin/export?domain=...`` which returns
a CSV of the orders log for the domain. The JS renderer wires this as
a download anchor.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote

_log = logging.getLogger("mycite.portal_host")

from ._shared import _as_dict, _as_text, _grantee_edit_link, _mask_secret


def _export_action(domain: str) -> dict[str, Any]:
    if not domain:
        return {}
    return {
        "label": "Export CSV",
        "href": f"/__fnd/paypal/admin/export?domain={quote(domain, safe='')}",
        "download": f"paypal-orders-{domain}.csv",
        "variant": "secondary",
    }


def _build_paypal_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,  # accepted, no longer used (no MOS)
    portal_instance_id: str | None = None,        # accepted, no longer used (no MOS)
) -> dict[str, Any]:
    """PayPal dashboard payload sourced ENTIRELY from instance-specific files —
    no MOS. The webhook URL is the canonical inline ``grantee.paypal.webhook_url``
    (operator-edited in the grantee profile); the recent-orders log is read from
    the instance NDJSON ledger. ``authority_db_file``/``portal_instance_id`` are
    retained in the signature for call-site compatibility but are unused.
    """
    orders: list[dict[str, Any]] = []

    # Canonical webhook source: the inline grantee paypal sub-config (instance
    # file). No MOS adapter, no paypal-webhook.<msn>.json sidecar fallback.
    paypal_subconfig = _as_dict(grantee.get("paypal"))
    webhook_url = _as_text(paypal_subconfig.get("webhook_url"))

    def _paypal_configuration() -> dict[str, Any]:
        # Surface the active MECHANISM up front so the operator can see, at a
        # glance, which of link / order / subscription is live for this grantee
        # without opening the editor: mode=link uses payment_link; mode=rest with
        # a plan_id is a recurring subscription, without one is a one-time order.
        mode = _as_text(paypal_subconfig.get("mode")) or (
            "rest" if _as_text(paypal_subconfig.get("client_secret")) else "link"
        )
        plan_id = _as_text(paypal_subconfig.get("plan_id"))
        if mode == "link":
            mechanism = "link (hosted payment link)"
        elif plan_id:
            mechanism = "subscription (recurring)"
        else:
            mechanism = "order (one-time)"
        return {
            "label": "PayPal configuration",
            "summary": "Active mechanism, webhook, credentials, and environment. Edit in the Grantee Profile.",
            "items": [
                {"label": "Mechanism", "value": mechanism},
                {"label": "Mode", "value": mode},
                {"label": "Payment link (link mode)", "value": _as_text(paypal_subconfig.get("payment_link"))},
                {"label": "Subscription plan ID", "value": plan_id},
                {"label": "Webhook URL", "value": _as_text(paypal_subconfig.get("webhook_url")) or webhook_url},
                {"label": "Environment", "value": _as_text(paypal_subconfig.get("environment")) or "sandbox"},
                {"label": "Client ID", "value": _as_text(paypal_subconfig.get("client_id"))},
                {"label": "Client secret", "value": _mask_secret(paypal_subconfig.get("client_secret"))},
            ],
            "edit_link": _grantee_edit_link("paypal"),
        }

    # Recent-orders log: instance NDJSON ledger (most-recent-first, capped).
    if private_dir is not None:
        orders_path = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
        try:
            if orders_path.exists():
                lines = orders_path.read_text(encoding="utf-8").splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        order = json.loads(line)
                        if not domain or _as_text(order.get("domain")).lower() == domain.lower():
                            orders.append({
                                "event": _as_text(order.get("event")),
                                "order_id": _as_text(order.get("order_id")),
                                "amount": _as_text(order.get("amount")),
                                "currency": _as_text(order.get("currency_code")),
                                "status": _as_text(order.get("status")),
                                "timestamp_ms": order.get("timestamp_ms"),
                                "domain": _as_text(order.get("domain")),
                            })
                            if len(orders) >= 30:
                                break
                    except Exception:
                        _log.warning("paypal_order_line_parse_failed", exc_info=True)
        except Exception:
            _log.warning("paypal_orders_ndjson_read_failed", exc_info=True)

    return {
        "domain": domain,
        "webhook_url": webhook_url,
        "orders": orders,
        "configuration": _paypal_configuration(),
        "export_action": _export_action(domain),
    }


__all__ = [
    "_build_paypal_extension_payload",
]
