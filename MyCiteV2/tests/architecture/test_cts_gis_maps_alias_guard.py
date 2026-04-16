from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCAN_ROOT = REPO_ROOT / "MyCiteV2"
ALLOWED_PATHS = {
    "packages/ports/datum_store/cts_gis_legacy_compat.py",
    "tests/adapters/test_filesystem_system_datum_store_adapter.py",
}
LEGACY_SEGMENT = "map" + "s"
SCATTERED_LEGACY_TOKENS = (
    f"sandbox:{LEGACY_SEGMENT}:",
    f"sandbox/{LEGACY_SEGMENT}/",
    f"tool.{LEGACY_SEGMENT}.json",
    f"tool.*.{LEGACY_SEGMENT}.json",
    f'"tool_id": "{LEGACY_SEGMENT}"',
    f"/utilities/tools/{LEGACY_SEGMENT}",
)


class CtsGisMapsAliasGuardTests(unittest.TestCase):
    def test_legacy_maps_alias_usage_is_centralized(self) -> None:
        violations: list[str] = []
        for path in sorted(SCAN_ROOT.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(SCAN_ROOT).as_posix()
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in SCATTERED_LEGACY_TOKENS:
                if token not in text:
                    continue
                if relative in ALLOWED_PATHS:
                    continue
                violations.append(f"{relative} -> {token}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
