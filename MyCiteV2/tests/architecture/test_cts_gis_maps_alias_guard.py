from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCAN_ROOTS = (
    REPO_ROOT / "MyCiteV2",
    REPO_ROOT / "docs",
)
ALLOWED_PATH_PREFIXES = (
    "docs/audits/",
    "docs/personal_notes/",
)
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
    def test_legacy_maps_alias_tokens_are_removed_from_active_code_and_contract_docs(self) -> None:
        violations: list[str] = []
        for scan_root in SCAN_ROOTS:
            for path in sorted(scan_root.rglob("*")):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts:
                    continue
                relative = path.relative_to(REPO_ROOT).as_posix()
                if any(relative.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES):
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                for token in SCATTERED_LEGACY_TOKENS:
                    if token in text:
                        violations.append(f"{relative} -> {token}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
