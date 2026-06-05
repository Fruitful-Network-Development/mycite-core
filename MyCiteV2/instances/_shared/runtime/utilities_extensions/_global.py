"""Global ("Overall") mode helpers for Utilities extensions.

Introduces the no-grantee "overall" view that complements the existing
per-grantee view. Every extension can be browsed across the whole grantee
roster (global mode) and then narrowed to one grantee on selection
(grantee mode) — the operator's "access each extension resource overall but
engage a per-grantee view upon selection" model.

Contract:
  * A renderer is in GLOBAL mode iff ``_as_text(ctx.get("mode")) == "global"``.
    ``_build_utilities_surface_context`` sets this when the operator picks the
    synthetic "All — Overall" selector entry, or on a fresh load of the
    Extensions surface (which defaults to global).
  * In global mode ``ctx["grantee"]`` is an EMPTY dict and ``ctx["domain"]`` is
    ``""``; the full roster rides in ``ctx["grantees"]`` for aggregation.
  * The per-grantee path is unchanged: ``ctx["mode"] == "grantee"`` (or the key
    being absent, as in the parity test's empty-ctx probe) keeps today's
    behavior exactly — so live email/payment/newsletter tooling cannot regress.

Global views are read-mostly and reuse each extension's existing per-grantee
builder via :func:`for_each_grantee`, which yields a per-grantee clone of the
ctx with ``mode="grantee"`` — no per-extension logic is duplicated.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ._shared import _as_text


def is_global(ctx: dict[str, Any]) -> bool:
    """True when the surface resolved to the no-grantee "Overall" view."""
    return _as_text(ctx.get("mode")) == "global"


def global_stub(label: str) -> dict[str, Any]:
    """Placeholder global payload used until an extension's overall view lands.

    Replaced by a real ``_build_*_overall`` in a later phase; keeps global mode
    coherent (and clearly labelled) without rendering a confusing empty
    per-grantee card.
    """
    return {
        "mode": "global",
        "overall_pending": True,
        "notice": (
            f"{label}: the Overall (all-grantees) view is coming soon. "
            "Select a grantee above to manage it individually."
        ),
    }


def enumerate_grantees(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the full grantee roster for aggregation.

    Prefers ``ctx["grantees"]`` (populated in global mode); falls back to
    loading from ``ctx["private_dir"]`` so the helper is usable even if a
    caller forgot to thread the roster.
    """
    grantees = ctx.get("grantees")
    if isinstance(grantees, list) and grantees:
        return grantees
    private_dir = ctx.get("private_dir")
    if private_dir is None:
        return []
    from MyCiteV2.instances._shared.runtime.operational_store import (
        load_grantee_profiles,
    )

    return load_grantee_profiles(private_dir)


def for_each_grantee(
    ctx: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], str, dict[str, Any]]]:
    """Yield ``(grantee, domain, sub_ctx)`` for every grantee/domain pair.

    ``sub_ctx`` is a shallow clone of ``ctx`` with ``grantee``/``domain`` filled
    and ``mode="grantee"`` (and ``grantees`` dropped), so a global view can call
    the SAME per-grantee builder used in single-grantee mode and concatenate the
    results. A grantee with no domains yields one row with ``domain=""``.
    """
    for grantee in enumerate_grantees(ctx):
        domains = [d for d in (grantee.get("domains") or []) if _as_text(d)]
        if not domains:
            domains = [""]
        for domain in domains:
            sub_ctx = dict(ctx)
            sub_ctx["grantee"] = grantee
            sub_ctx["domain"] = _as_text(domain)
            sub_ctx["mode"] = "grantee"
            sub_ctx.pop("grantees", None)
            yield grantee, _as_text(domain), sub_ctx


__all__ = ["enumerate_grantees", "for_each_grantee", "global_stub", "is_global"]
