from __future__ import annotations

# Backward-compatible shim. Canonical shared implementation now lives under
# instances/_shared/portal/sandbox/samras.py.
#
# IMPORTANT:
# SAMRAS structure addressing is NOT the same context as anthology/resource
# datum addresses (<layer>-<value_group>-<iteration>) and is also distinct from
# MSS compact-array transport indexes.
# See:
# - datum_structure.py
# - mss_compact_array_reference.py
try:  # pragma: no cover - import path depends on caller setup
    from _shared.portal.sandbox.samras import *  # noqa: F401,F403
except Exception:  # pragma: no cover - package callers may only expose repo root
    from instances._shared.portal.sandbox.samras import *  # noqa: F401,F403
