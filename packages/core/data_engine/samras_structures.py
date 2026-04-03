from __future__ import annotations

# Backward-compatible shim. Canonical shared implementation now lives under
# portals/_shared/portal/sandbox/samras.py.
#
# IMPORTANT:
# SAMRAS structure addressing is NOT the same context as anthology/resource
# datum addresses (<layer>-<value_group>-<iteration>) and is also distinct from
# MSS compact-array transport indexes.
# See:
# - datum_structure.py
# - mss_compact_array_reference.py
from portals._shared.portal.sandbox.samras import *  # noqa: F401,F403