from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TARGETS = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "admin_fnd_ebi_runtime.py",
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "app.py",
    REPO_ROOT / "MyCiteV2" / "packages" / "adapters" / "filesystem" / "fnd_ebi_read_only.py",
    REPO_ROOT / "MyCiteV2" / "packages" / "modules" / "cross_domain" / "fnd_ebi" / "service.py",
)


class FndEbiReadOnlyBoundaryTests(unittest.TestCase):
    def test_fnd_ebi_slice_stays_free_of_calendar_and_progeny_placeholder_leakage(self) -> None:
        violations: list[str] = []

        for path in TARGETS:
            text = path.read_text(encoding="utf-8")
            for token in (
                "tenant_progeny_profiles",
                "progeny_workbench",
                '"tool_id": "calendar"',
                "tool_id='calendar'",
                'tool_id = "calendar"',
            ):
                if token in text:
                    violations.append(f"{path.name}: forbidden token {token}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
