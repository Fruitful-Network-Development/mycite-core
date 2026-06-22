"""Single atomic temp-then-replace file writer for every leaflet / manifest /
config / state writer in the codebase.

Before this, ~8 modules each carried their own copy of the mkstemp + write +
``os.replace`` dance, and they had drifted: only some preserved the
destination's mode, so a served file (record-manifest, profile YAML, static
page) re-saved through a copy that left ``mkstemp``'s 0600 became unreadable to
nginx (the worker runs as ``admin``) and its URL started returning 403. Others
omitted ``fsync``. Consolidating means the served-perms fix and the durability
flush live in exactly one place.

``mode`` selects the permission policy, because the writers split into two
classes that must NOT be merged:

* ``PRESERVE`` (default) — keep the destination's existing mode, defaulting a
  new file to 0644. For anything nginx serves.
* ``KEEP`` — leave ``mkstemp``'s 0600 untouched. For private state and secrets
  (operator ledgers, lens state, AWS CSM credentials) that must stay 0600.

An explicit ``int`` forces exactly that mode.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

PRESERVE = "preserve"
KEEP = "keep"


def _resolved_mode(path: Path, mode: Any) -> int | None:
    if mode == KEEP:
        return None  # leave the mkstemp 0600 in place
    if mode == PRESERVE:
        try:
            return os.stat(path).st_mode & 0o777  # keep the served file readable
        except FileNotFoundError:
            return 0o644  # readable default for a new served file
    return int(mode)


def atomic_write_bytes(path, data: bytes, *, mode: Any = PRESERVE, fsync: bool = True) -> None:
    """Atomically write ``data`` to ``path`` (temp in the same dir + os.replace).
    A torn write can never replace a good file. See the module docstring for
    ``mode``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            if fsync:
                handle.flush()
                os.fsync(handle.fileno())
        resolved = _resolved_mode(path, mode)
        if resolved is not None:
            os.chmod(tmp, resolved)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_text(
    path, text: str, *, mode: Any = PRESERVE, encoding: str = "utf-8", fsync: bool = True
) -> None:
    """Atomic text write. See :func:`atomic_write_bytes`."""
    atomic_write_bytes(path, text.encode(encoding), mode=mode, fsync=fsync)


def atomic_write_yaml(
    path, data: Any, *, mode: Any = PRESERVE, sort_keys: bool = False, allow_unicode: bool = True
) -> None:
    """Atomic YAML write (``yaml.safe_dump``). See :func:`atomic_write_bytes`."""
    import yaml

    atomic_write_text(
        path,
        yaml.safe_dump(data, sort_keys=sort_keys, allow_unicode=allow_unicode),
        mode=mode,
    )
