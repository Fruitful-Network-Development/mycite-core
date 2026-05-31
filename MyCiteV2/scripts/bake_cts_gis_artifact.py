"""Lean offline bake for the CTS-GIS compiled artifact's projection model.

Reads the CTS-GIS geometry documents straight from MOS, runs datum recognition
+ the surviving ``_build_document_projection`` HOPS decode, merges every decoded
GeoJSON feature into one ``FeatureCollection``, and writes it into the served
compiled artifact's ``projection_model`` — the only thing the thin ``cts_gis``
map tool reads (``packages/tools/cts_gis_map.py``). The district/admin thin tools
read MOS-direct, so they need no bake; this refreshes their static blocks in the
artifact for parity only.

This replaces the deleted heavy ``compile_cts_gis_artifact.py``, which drove the
now-removed ``portal_cts_gis_runtime`` ``force_live_read`` path (~35s / ~700MB).
It imports ONLY surviving modules: the SQL datum store, ``datum_recognition``,
``cts_gis._projection``, and ``compiled_artifact``'s path/read/write helpers.

The geometry IS in MOS: 85 precinct docs (``247_17_77_*``) carry HOPS-encoded
coordinate rings, and ~33 SAMRAS node docs (``3-2-3-17-*``) carry the county/state
aggregate boundaries. The frozen artifact showed 0 features only because the
recompile was never re-run after the disk-source path was retired.

Usage:
  python bake_cts_gis_artifact.py \
      --data-dir /srv/webapps/mycite/fnd/data \
      --authority-db /srv/webapps/mycite/fnd/private/mos_authority.sqlite3 \
      [--scope-id fnd] [--dry-run]

``--dry-run`` reports the bake (feature count, bounds) without touching the served
artifact. Without it, the served artifact is backed up (``.bake-prev.bak``) then
updated in place; the bake aborts (leaving the served artifact untouched) if it
decodes zero features.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.cts_gis.compiled_artifact import (
    compiled_artifact_path,
    read_admin_profile_static_from_mos,
    read_compiled_artifact,
    read_district_profile_static_from_mos,
    write_compiled_artifact,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis._projection import (
    _build_document_projection,
)
from MyCiteV2.packages.modules.domains.datum_recognition.service import (
    recognize_authoritative_document,
)
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

# Big MOS index docs in the cts_gis sandbox that carry no polygon geometry
# (recognizing the 41k-row address index would be slow and pointless).
_NON_GEOMETRY_DOCS = frozenset({"address_nodes", "administrative", "sos_voterid"})


def _is_cts_gis_document(document: Any) -> bool:
    parts = str(getattr(document, "document_id", "")).split(".")
    return len(parts) > 2 and parts[2] == "cts_gis"


def _bake_projection_model(store: Any, tenant_id: str) -> dict[str, Any]:
    """Decode every CTS-GIS geometry doc in MOS into one GeoJSON FeatureCollection."""
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
    )
    geometry_docs = [
        document
        for document in catalog.documents
        if _is_cts_gis_document(document)
        and getattr(document, "canonical_name", "") not in _NON_GEOMETRY_DOCS
    ]

    features: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    bounds_acc: list[list[float]] = []
    contributing = 0
    for document in geometry_docs:
        recognized = recognize_authoritative_document(document)
        projection = _build_document_projection(recognized, overlay_mode="decoded")
        doc_features = projection.get("feature_index") or {}
        if doc_features:
            contributing += 1
        for entry in doc_features.values():
            feature = entry.get("feature")
            feature_id = str(entry.get("feature_id") or "")
            if not isinstance(feature, dict) or feature_id in seen_ids:
                continue
            seen_ids.add(feature_id)
            features.append(feature)
            row_bounds = entry.get("bounds")
            if isinstance(row_bounds, list) and len(row_bounds) == 4:
                bounds_acc.append([float(value) for value in row_bounds])

    focus_bounds: list[float] = []
    if bounds_acc:
        focus_bounds = [
            min(b[0] for b in bounds_acc),
            min(b[1] for b in bounds_acc),
            max(b[2] for b in bounds_acc),
            max(b[3] for b in bounds_acc),
        ]

    return {
        "feature_collection": {"type": "FeatureCollection", "features": features},
        "feature_count": len(features),
        "focus_bounds": focus_bounds,
        "projection_state": "ready" if features else "empty",
        "projection_source": "mos_hops_bake",
        # Diagnostics for the bake audit trail (ignored by the thin map tool).
        "bake_diagnostics": {
            "documents_scanned": len(geometry_docs),
            "documents_with_geometry": contributing,
        },
    }


def _skeleton_artifact(scope_id: str) -> dict[str, Any]:
    """Minimal artifact when none is served yet (the map tool reads projection_model)."""
    return {
        "schema": "mycite.v2.cts_gis.compiled_artifact.v1",
        "portal_scope_id": scope_id,
        "navigation_model": {},
        "projection_model": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Portal data directory (compiled-artifact root).")
    parser.add_argument("--authority-db", required=True, help="Path to mos_authority.sqlite3.")
    parser.add_argument("--scope-id", default="fnd", help="Portal scope / tenant id (default: fnd).")
    parser.add_argument("--dry-run", action="store_true", help="Report the bake without writing the served artifact.")
    args = parser.parse_args()

    served_path = compiled_artifact_path(args.data_dir, portal_scope_id=args.scope_id)
    if served_path is None:
        print("error: could not resolve compiled-artifact path from --data-dir", file=sys.stderr)
        return 2

    store = SqliteSystemDatumStoreAdapter(args.authority_db, allow_legacy_writes=False)

    projection_model = _bake_projection_model(store, args.scope_id)
    feature_count = projection_model["feature_count"]
    diagnostics = projection_model["bake_diagnostics"]
    print(
        f"baked {feature_count} features from {diagnostics['documents_with_geometry']}"
        f"/{diagnostics['documents_scanned']} geometry docs; bounds={projection_model['focus_bounds']}"
    )

    if feature_count == 0:
        print("error: bake decoded 0 features — refusing to overwrite the served artifact", file=sys.stderr)
        return 1

    # Refresh the static profile blocks (read MOS-direct by the thin tools, kept
    # in the artifact for parity with the old compile validator).
    district_static = read_district_profile_static_from_mos(store, tenant_id=args.scope_id) or {}
    admin_static = read_admin_profile_static_from_mos(store, tenant_id=args.scope_id) or {}

    base = read_compiled_artifact(served_path) or _skeleton_artifact(args.scope_id)
    base["projection_model"] = projection_model
    base["district_profile_static"] = district_static
    base["admin_profile_static"] = admin_static
    navigation = dict(base.get("navigation_model") or {})
    navigation["decode_state"] = "ready"
    base["navigation_model"] = navigation
    base["generated_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    base["build_mode"] = "mos_lean_bake"

    if args.dry_run:
        print(f"dry-run: would write {feature_count} features to {served_path} (served artifact untouched)")
        return 0

    if served_path.exists():
        backup_path = served_path.with_suffix(served_path.suffix + ".bake-prev.bak")
        shutil.copy2(served_path, backup_path)
        print(f"backed up served artifact → {backup_path}")

    written = write_compiled_artifact(served_path, base)
    print(f"wrote {feature_count} features to {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
