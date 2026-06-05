#!/usr/bin/env python3
"""migrate_bpw_jobs_to_events — port the legacy BPW job corpus to the
shared ``event-job`` leaflet gallery.

Reads every ``job.<date>.<slug>.yaml`` under the legacy jobs root
(default ``/srv/webapps/mycite/fnd/private/utilities/tools/bpw-jobs/``)
and writes one ``event-job`` leaflet per job into the shared events
gallery::

    <events_root>/<yyyy-mm-dd>.event-job.<client>.<slug>.yaml

where ``client`` defaults to ``brocks_pressure_washing``. Each leaflet is
stamped with schema ``mycite.site_core.event_job.v1`` and
``event_kind: job``. The legacy nested ``job.{id,date,status}`` is
promoted to the reconciled top-level envelope (id / date / status /
title / location / description / leaflet_url), with ``customer.address``
-> ``location``, ``notes`` -> ``description`` and a derived ``title``;
the job-kind extras (customer / home / tags / pricing) stay nested.

The migration is IDEMPOTENT: re-running over an already-migrated gallery
re-derives the same filenames and content (modulo the schema/kind/client
stamp), so it can be run repeatedly without producing duplicates.

Safety:
  * ``--dry-run`` (the DEFAULT) prints what WOULD be written and touches
    nothing.
  * ``--apply`` performs the writes and first takes a ``.bak`` copy of
    the source jobs directory.

PII: the source jobs + the written leaflets contain customer data. They
are RUNTIME state and must NEVER be committed to git. The live --apply
run against production data is a post-merge operator step.
"""

from __future__ import annotations

import argparse
import glob
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions import events as _events

DEFAULT_JOBS_ROOT = Path(
    "/srv/webapps/mycite/fnd/private/utilities/tools/bpw-jobs"
)
DEFAULT_WEBAPPS_ROOT = Path("/srv/webapps")
DEFAULT_CLIENT = "brocks_pressure_washing"


def _load_yaml(path: Path) -> dict[str, Any] | None:
    return _events._load_yaml(path)


def _derive_title(customer: dict[str, Any], tags: Any, event_id: str) -> str:
    """Derive a generic display title for a migrated job leaflet.

    Prefer "<first-tag-type humanized> — <customer name>" (e.g.
    "House wash — Dave Atch"); fall back to the customer name alone, and
    finally to the event id.
    """
    name = str(customer.get("name") or "").strip()
    first_tag = ""
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, dict) and t.get("type"):
                first_tag = str(t["type"]).strip()
                break
    label = first_tag.replace("_", " ").strip().capitalize()
    if label and name:
        return f"{label} — {name}"
    if name:
        return name
    return str(event_id or "")


def _to_event_leaflet(job_doc: dict[str, Any], client: str) -> dict[str, Any]:
    """Build the on-disk event-job leaflet from a legacy job document.

    Promotes the legacy nested ``job.{id,date,status}`` to the
    reconciled top-level envelope, maps ``customer.address`` -> top-level
    ``location`` and ``notes`` -> ``description``, derives a generic
    ``title``, and preserves the job-kind extras
    (``customer`` / ``home`` / ``tags`` / ``pricing``) nested.
    ``_source_file`` (a runtime-only read annotation) is dropped.
    """
    doc = {k: v for k, v in job_doc.items() if k != "_source_file"}
    job = doc.get("job") if isinstance(doc.get("job"), dict) else {}
    customer = doc.get("customer") if isinstance(doc.get("customer"), dict) else {}
    tags = doc.get("tags") if isinstance(doc.get("tags"), list) else []
    notes = doc.get("notes") or ""

    event_id = str(job.get("id") or "")
    title = _derive_title(customer, tags, event_id)

    leaflet: dict[str, Any] = {
        "schema": _events.EVENT_SCHEMA,
        "event_kind": _events.DEFAULT_EVENT_KIND,
        "client": _events._client_slug(client),
        "id": event_id,
        "date": str(job.get("date") or ""),
        "status": str(job.get("status") or "booked"),
        "title": title,
        "location": str(customer.get("address") or ""),
        "description": str(notes or ""),
        "leaflet_url": doc.get("leaflet_url") or None,
    }
    # Carry the nested job-kind extras (minus the now-promoted ``job``).
    for section in ("customer", "home", "tags", "pricing", "notes"):
        if section in doc:
            leaflet[section] = doc[section]
    # Preserve any extra sections not already mapped (skip the legacy
    # ``job`` wrapper — its fields are promoted to the top level above).
    for key, value in doc.items():
        if key == "job":
            continue
        if key not in leaflet:
            leaflet[key] = value
    return leaflet


def _target_filename(leaflet: dict[str, Any]) -> str:
    """Canonical event-job filename for a leaflet (reuses the events
    module's slug/filename convention)."""
    return _events._filename_for(leaflet)


def migrate(
    *,
    jobs_root: Path,
    webapps_root: Path,
    client: str,
    apply: bool,
) -> dict[str, Any]:
    """Run the migration. Returns a summary dict. When ``apply`` is
    False, only plans the work (no disk writes)."""
    jobs_root = Path(jobs_root)
    sources = sorted(glob.glob(str(jobs_root / "job.*.yaml")))
    events_dir = _events.events_root(webapps_root)

    planned: list[tuple[str, str]] = []  # (source_name, target_name)
    skipped: list[str] = []
    by_target: dict[str, list[str]] = {}
    for src in sources:
        src_path = Path(src)
        doc = _load_yaml(src_path)
        if doc is None:
            skipped.append(src_path.name)
            continue
        leaflet = _to_event_leaflet(doc, client)
        target = _target_filename(leaflet)
        planned.append((src_path.name, target))
        by_target.setdefault(target, []).append(src_path.name)

    # Two distinct source jobs that slug to the same target filename would
    # silently overwrite each other on --apply, dropping a job. Surface it
    # as a hard collision the operator must resolve (e.g. rename a source)
    # rather than losing PII data.
    collisions = {t: names for t, names in by_target.items() if len(names) > 1}

    summary: dict[str, Any] = {
        "jobs_root": str(jobs_root),
        "events_dir": str(events_dir),
        "client": _events._client_slug(client),
        "source_count": len(sources),
        "planned_count": len(planned),
        "skipped_unreadable": skipped,
        "collisions": collisions,
        "applied": False,
        "backup_dir": None,
    }

    if not apply:
        summary["planned"] = planned
        return summary

    if collisions:
        # Refuse to write anything when target names would clash.
        raise SystemExit(
            "migration aborted: multiple source jobs map to the same "
            f"target filename(s): {collisions}"
        )

    # --apply: back up the source dir once, then write the leaflets.
    # Idempotent: if a prior apply already left a .pre-events-*.bak next
    # to the source dir, reuse it rather than stacking a fresh copy (or
    # colliding on a same-second timestamp) on re-run.
    if jobs_root.exists():
        existing_backups = sorted(
            glob.glob(str(jobs_root.with_name(f"{jobs_root.name}.pre-events-*.bak")))
        )
        if existing_backups:
            summary["backup_dir"] = existing_backups[0]
        else:
            stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            backup_dir = jobs_root.with_name(
                f"{jobs_root.name}.pre-events-{stamp}.bak"
            )
            shutil.copytree(jobs_root, backup_dir)
            summary["backup_dir"] = str(backup_dir)

    events_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for src in sources:
        src_path = Path(src)
        doc = _load_yaml(src_path)
        if doc is None:
            continue
        leaflet = _to_event_leaflet(doc, client)
        target_path = events_dir / _target_filename(leaflet)
        _events._atomic_write_yaml(target_path, leaflet)
        written.append(target_path.name)

    summary["applied"] = True
    summary["written"] = written
    summary["written_count"] = len(written)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--jobs-root",
        type=Path,
        default=DEFAULT_JOBS_ROOT,
        help="Legacy BPW jobs directory (job.*.yaml).",
    )
    p.add_argument(
        "--webapps-root",
        type=Path,
        default=DEFAULT_WEBAPPS_ROOT,
        help="Webapps root; events land in clients/_shared/site-core/events/.",
    )
    p.add_argument(
        "--client",
        default=DEFAULT_CLIENT,
        help="Client slug stamped on each event leaflet.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Plan only; write nothing (DEFAULT).",
    )
    mode.add_argument(
        "--apply",
        dest="apply",
        action="store_true",
        help="Perform the migration (backs up the source dir first).",
    )
    p.set_defaults(apply=False)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = migrate(
        jobs_root=args.jobs_root,
        webapps_root=args.webapps_root,
        client=args.client,
        apply=args.apply,
    )

    mode = "APPLY" if summary["applied"] else "DRY-RUN"
    print(f"[{mode}] BPW jobs -> events migration")
    print(f"  jobs_root : {summary['jobs_root']}")
    print(f"  events_dir: {summary['events_dir']}")
    print(f"  client    : {summary['client']}")
    print(f"  sources   : {summary['source_count']}")
    if summary["skipped_unreadable"]:
        print(f"  skipped   : {len(summary['skipped_unreadable'])} unreadable")
        for name in summary["skipped_unreadable"]:
            print(f"              - {name}")
    if summary.get("collisions"):
        print(f"  COLLISIONS: {len(summary['collisions'])} target name(s) clash")
        for target, names in summary["collisions"].items():
            print(f"              {target} <- {names}")
        print("              (--apply will REFUSE until resolved)")
    if summary["applied"]:
        if summary["backup_dir"]:
            print(f"  backup    : {summary['backup_dir']}")
        print(f"  written   : {summary['written_count']} leaflets")
    else:
        print(f"  planned   : {summary['planned_count']} leaflets (no writes)")
        for src_name, target_name in summary.get("planned", []):
            print(f"    {src_name}  ->  {target_name}")
        print("\n  (dry-run — pass --apply to write; it backs up the source dir)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
