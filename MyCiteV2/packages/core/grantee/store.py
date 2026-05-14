"""Filesystem store for GranteeProfile.

Read: ``load_grantee_profile(path) -> GranteeProfile``
Write: ``save_grantee_profile(path, profile, *, allow_overwrite=True)``

Writes are atomic: serialize to a temp file in the same directory, ``fsync``
the file, then ``os.replace`` it into the target name so a crash mid-write
never leaves a half-written grantee JSON on disk. The atomicity contract
matters because the file is the source of truth for credentials read by
the next portal request — a torn write would surface as missing creds in
the Utilities extensions.

No process-wide state. Each call opens and closes its own file handle.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .schema import GranteeProfile


class GranteeProfileWriteError(RuntimeError):
    """Raised when a grantee profile cannot be persisted."""


def load_grantee_profile(path: str | Path) -> GranteeProfile:
    """Parse a grantee JSON file from disk.

    Raises:
        FileNotFoundError when the path does not exist.
        ValueError when the JSON is malformed or the schema is wrong.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"grantee profile not found: {file_path}")
    raw = file_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"grantee profile is not valid JSON: {file_path} ({exc})") from exc
    return GranteeProfile.from_dict(payload)


def save_grantee_profile(
    path: str | Path,
    profile: GranteeProfile,
    *,
    allow_overwrite: bool = True,
) -> None:
    """Persist ``profile`` to ``path`` atomically.

    Args:
        path: Destination grantee JSON file.
        profile: Validated GranteeProfile.
        allow_overwrite: When False, refuse to clobber an existing file.

    Raises:
        GranteeProfileWriteError when the temp file cannot be created or the
        rename into place fails.
        FileExistsError when allow_overwrite is False and ``path`` exists.
    """
    file_path = Path(path)
    if file_path.exists() and not allow_overwrite:
        raise FileExistsError(f"refusing to overwrite existing grantee profile: {file_path}")

    parent = file_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    payload = profile.to_dict()
    serialized = json.dumps(payload, indent=2, sort_keys=False) + "\n"

    # Atomic write: temp file in same directory + os.replace.
    temp_fd, temp_name = tempfile.mkstemp(prefix=".grantee_", suffix=".tmp", dir=str(parent))
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as fp:
            fp.write(serialized)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp_name, file_path)
    except OSError as exc:
        # Best-effort cleanup of the orphaned temp file.
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise GranteeProfileWriteError(f"failed to save grantee profile {file_path}: {exc}") from exc


__all__ = [
    "GranteeProfileWriteError",
    "load_grantee_profile",
    "save_grantee_profile",
]
