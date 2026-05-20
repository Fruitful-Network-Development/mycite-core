"""Architecture invariant: no canonical datum documents on disk.

The MOS authority database is the SOLE storage for canonical datum
documents (see ``docs/contracts/datum_document_naming_taxonomy.md:181-209``
and the consolidated ``docs/contracts/mos_authority_enforcement.md``).
This test fails if any JSON/.bin file matching datum-doc shapes appears
under ``$LIVE_FND_DATA_DIR/{system,sandbox,payloads/cache}/``.

Compiled UI surface payloads under ``data/payloads/compiled/`` are
exempt. Evidence and legacy-staging artifacts under
``/srv/agentic/evidence/`` are not part of the live tree and not checked.
"""

from __future__ import annotations

import unittest
from pathlib import Path

LIVE_FND_DATA_DIR = Path("/srv/webapps/mycite/fnd/data")

# Filename shapes that look like a datum document
_FORBIDDEN_PREFIXES = ("lv.", "sc.", "cptr.", "stl.", "rf.", "tool.")
_FORBIDDEN_LITERAL_NAMES = {"anthology.json", "system_log.json"}
_FORBIDDEN_SUFFIXES = (".pre-repair", ".pre-compile")

# Directories that must be free of canonical datum content
_FORBIDDEN_PARENT_DIRS = ("system", "sandbox", "payloads/cache", "payloads")

# Allowed exceptions under data/
_ALLOWED_RELATIVE = {
    "payloads/compiled/cts_gis.fnd.compiled.json",
}


class NoDiskDatumAuthoritiesTest(unittest.TestCase):
    def _live_dir(self) -> Path:
        if not LIVE_FND_DATA_DIR.exists():
            self.skipTest(f"live FND data dir not present: {LIVE_FND_DATA_DIR}")
        return LIVE_FND_DATA_DIR

    # Required invariant. Disk archival landed 2026-05-17.
    def test_no_datum_doc_files_under_fnd_data(self) -> None:
        data_dir = self._live_dir()
        violations: list[str] = []
        for parent in _FORBIDDEN_PARENT_DIRS:
            root = data_dir / parent
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(data_dir).as_posix()
                if rel in _ALLOWED_RELATIVE:
                    continue
                name = path.name
                if name in _FORBIDDEN_LITERAL_NAMES:
                    violations.append(rel)
                    continue
                if any(name.startswith(p) for p in _FORBIDDEN_PREFIXES):
                    violations.append(rel)
                    continue
                if any(s in name for s in _FORBIDDEN_SUFFIXES):
                    violations.append(rel)
                    continue
                if name.endswith(".bin"):
                    violations.append(rel)
                    continue
        self.assertEqual(
            violations,
            [],
            f"{len(violations)} disk artifacts violate MOS-only doctrine. First 5: {violations[:5]}",
        )

    def test_no_extra_sqlite_databases_under_fnd(self) -> None:
        """The MOS authority is at ``private/mos_authority.sqlite3``. Any
        other ``*.sqlite3`` file under the live FND tree contradicts the
        single-authority rule. This test catches the empty
        ``fnd_portal_authority.sqlite3`` and any future parallel DBs.
        """
        fnd_root = LIVE_FND_DATA_DIR.parent
        if not fnd_root.exists():
            self.skipTest(f"live FND root not present: {fnd_root}")
        allowed = {(fnd_root / "private" / "mos_authority.sqlite3").resolve()}
        extras: list[str] = []
        for path in fnd_root.rglob("*.sqlite3"):
            if path.resolve() in allowed:
                continue
            extras.append(str(path.relative_to(fnd_root)))
        self.assertEqual(
            extras,
            [],
            f"Extra sqlite3 file(s) under fnd/: {extras}",
        )

    def test_compiled_ui_payloads_are_not_datum_documents(self) -> None:
        """``data/payloads/compiled/*.json`` is allowed only for compiled
        UI surface payloads. Assert these files contain NO row-shape
        like ``raw[0]``/``raw[1]`` characteristic of datum documents.
        """
        compiled_dir = LIVE_FND_DATA_DIR / "payloads" / "compiled"
        if not compiled_dir.exists():
            self.skipTest(f"compiled dir not present: {compiled_dir}")
        import json
        for path in compiled_dir.glob("*.json"):
            with path.open() as f:
                doc = json.load(f)
            if isinstance(doc, dict):
                for key, value in doc.items():
                    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], list) and isinstance(value[1], list):
                        self.fail(
                            f"{path.relative_to(compiled_dir.parent.parent)} key {key!r} "
                            f"has datum-doc row shape; compiled payloads must not contain datum content."
                        )


if __name__ == "__main__":
    unittest.main()
