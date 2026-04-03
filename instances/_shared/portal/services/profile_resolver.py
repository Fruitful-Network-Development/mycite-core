from __future__ import annotations

from pathlib import Path


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _candidate_paths(*, root: Path, msn_id: str, include_fnd: bool) -> list[Path]:
    token = _as_text(msn_id)
    if not token:
        return []
    items = [
        root / f"{token}.json",
        root / f"msn-{token}.json",
        root / f"mss-{token}.json",
    ]
    if include_fnd:
        items.append(root / f"fnd-{token}.json")
    return items


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def resolve_public_profile_path(*, public_dir: Path, fallback_dir: Path | None, msn_id: str) -> Path | None:
    direct = _first_existing(_candidate_paths(root=public_dir, msn_id=msn_id, include_fnd=False))
    if direct is not None:
        return direct
    if isinstance(fallback_dir, Path):
        return _first_existing(_candidate_paths(root=fallback_dir, msn_id=msn_id, include_fnd=False))
    return None


def resolve_fnd_profile_path(*, public_dir: Path, fallback_dir: Path | None, msn_id: str) -> Path | None:
    token = _as_text(msn_id)
    if not token:
        return None
    candidates = [public_dir / f"fnd-{token}.json"]
    if isinstance(fallback_dir, Path):
        candidates.append(fallback_dir / f"fnd-{token}.json")
    return _first_existing(candidates)


def find_local_contact_card(*, public_dir: Path, fallback_dir: Path | None, msn_id: str, include_fnd: bool = False) -> Path | None:
    direct = _first_existing(_candidate_paths(root=public_dir, msn_id=msn_id, include_fnd=include_fnd))
    if direct is not None:
        return direct
    if isinstance(fallback_dir, Path):
        return _first_existing(_candidate_paths(root=fallback_dir, msn_id=msn_id, include_fnd=include_fnd))
    return None
