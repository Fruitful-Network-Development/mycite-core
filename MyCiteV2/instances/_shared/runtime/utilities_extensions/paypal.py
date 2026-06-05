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

from MyCiteV2.packages.core.grantee import PaypalConfig

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


def _hydrate_paypal_from_sidecar(
    private_dir: Path, msn_id: str
) -> PaypalConfig | None:
    """Read a legacy ``paypal-webhook.{msn_id}.json`` sidecar into a PaypalConfig.

    Phase 8 read-side backward compat: grantee JSON files written before
    the inline ``paypal`` sub-config landed will not carry credentials.
    If a sidecar file is present, hydrate the in-memory profile from it
    so the Utilities extensions render correctly. Returns ``None`` when
    no sidecar exists or its shape is unusable.
    """
    if not msn_id:
        return None
    sidecar_path = private_dir / "utilities" / "tools" / "fnd-csm" / f"paypal-webhook.{msn_id}.json"
    if not sidecar_path.exists():
        return None
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    webhook_url = _as_text(payload.get("webhook_url"))
    if not webhook_url:
        return None
    try:
        return PaypalConfig(webhook_url=webhook_url)
    except ValueError:
        return None


def _build_paypal_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    orders: list[dict[str, Any]] = []
    webhook_url = ""

    # Phase 8 (grantee_profile_contract.md): inline grantee.paypal.webhook_url
    # is the canonical source. MOS adapter + sidecar remain as fallbacks for
    # one transition cycle.
    grantee_paypal = _as_dict(grantee.get("paypal"))
    if grantee_paypal:
        webhook_url = _as_text(grantee_paypal.get("webhook_url"))

    if authority_db_file is not None:
        try:
            from MyCiteV2.packages.adapters.sql.fnd_paypal import (
                MosDatumPayPalOrdersAdapter,
                MosDatumPayPalWebhookAdapter,
            )

            orders_adapter = MosDatumPayPalOrdersAdapter(
                authority_db_file=authority_db_file,
                tenant_id=portal_instance_id or "fnd",
            )
            if domain:
                orders = orders_adapter.load_orders(domain=domain)
            # Phase 8: only consult the MOS webhook adapter when the grantee
            # JSON did not already supply a webhook_url. Grantee-inline wins.
            if not webhook_url:
                grantee_msn = _as_text(grantee.get("msn_id"))
                if grantee_msn:
                    webhook_adapter = MosDatumPayPalWebhookAdapter(
                        authority_db_file=authority_db_file,
                        tenant_id=portal_instance_id or "fnd",
                    )
                    hook = webhook_adapter.load_webhook(grantee_msn_id=grantee_msn)
                    if hook:
                        webhook_url = _as_text(hook.get("webhook_url"))
        except Exception:
            _log.warning("paypal_mos_orders_webhook_load_failed", exc_info=True)
            orders = []
            # Preserve a grantee-inline webhook_url even if the MOS adapter
            # threw; it was set before this try block ran.

    # Phase 10: build the configuration mirror up front so it's attached
    # to whichever return path executes (MOS shortcut or filesystem fallback).
    paypal_subconfig = _as_dict(grantee.get("paypal"))

    def _paypal_configuration() -> dict[str, Any]:
        return {
            "label": "PayPal configuration",
            "summary": "Webhook URL, client credentials, and environment. Edit in the Grantee Profile.",
            "items": [
                {"label": "Webhook URL", "value": _as_text(paypal_subconfig.get("webhook_url")) or webhook_url},
                {"label": "Environment", "value": _as_text(paypal_subconfig.get("environment")) or "sandbox"},
                {"label": "Client ID", "value": _as_text(paypal_subconfig.get("client_id"))},
                {"label": "Client secret", "value": _mask_secret(paypal_subconfig.get("client_secret"))},
            ],
            "edit_link": _grantee_edit_link("paypal"),
        }

    if orders or webhook_url:
        return {
            "domain": domain,
            "webhook_url": webhook_url,
            "orders": orders,
            "configuration": _paypal_configuration(),
            "export_action": _export_action(domain),
        }

    # Filesystem fallback (unchanged from the pre-MOS behavior).
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
                        pass
        except Exception:
            _log.warning("paypal_orders_ndjson_read_failed", exc_info=True)
            pass
        # Optional per-grantee webhook config — only consulted when no
        # grantee-inline webhook_url (Phase 8 precedence).
        if not webhook_url:
            msn_id = _as_text(grantee.get("msn_id"))
            webhook_path = Path(private_dir) / "utilities" / "tools" / "fnd-csm" / f"paypal-webhook.{msn_id}.json"
            try:
                if webhook_path.exists():
                    wh = json.loads(webhook_path.read_text(encoding="utf-8"))
                    webhook_url = _as_text(_as_dict(wh).get("webhook_url"))
            except Exception:
                _log.warning("paypal_webhook_sidecar_read_failed", exc_info=True)
                pass
    return {
        "domain": domain,
        "webhook_url": webhook_url,
        "orders": orders,
        "configuration": _paypal_configuration(),
        "export_action": _export_action(domain),
    }


def _render_ext_paypal(ctx: dict[str, Any]) -> dict[str, Any]:
    from ._global import global_stub, is_global

    if is_global(ctx):
        return global_stub("PayPal")
    return _build_paypal_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = [
    "_build_paypal_extension_payload",
    "_hydrate_paypal_from_sidecar",
    "_render_ext_paypal",
]
