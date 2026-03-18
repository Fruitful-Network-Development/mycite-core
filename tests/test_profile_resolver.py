from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

PORTALS_ROOT = Path(__file__).resolve().parents[1] / "portals"
if str(PORTALS_ROOT) not in sys.path:
    sys.path.insert(0, str(PORTALS_ROOT))

from _shared.portal.services.profile_resolver import (
    find_local_contact_card,
    resolve_fnd_profile_path,
    resolve_public_profile_path,
)


class ProfileResolverTests(unittest.TestCase):
    def test_public_profile_resolution_prefers_public_then_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            fallback_dir = root / "fallback"
            public_dir.mkdir(parents=True, exist_ok=True)
            fallback_dir.mkdir(parents=True, exist_ok=True)
            (fallback_dir / "msn-1-2-3.json").write_text("{}", encoding="utf-8")
            chosen = resolve_public_profile_path(public_dir=public_dir, fallback_dir=fallback_dir, msn_id="1-2-3")
            self.assertEqual(chosen, fallback_dir / "msn-1-2-3.json")
            (public_dir / "1-2-3.json").write_text("{}", encoding="utf-8")
            chosen2 = resolve_public_profile_path(public_dir=public_dir, fallback_dir=fallback_dir, msn_id="1-2-3")
            self.assertEqual(chosen2, public_dir / "1-2-3.json")

    def test_fnd_profile_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            fallback_dir = root / "fallback"
            public_dir.mkdir(parents=True, exist_ok=True)
            fallback_dir.mkdir(parents=True, exist_ok=True)
            (fallback_dir / "fnd-1-2-3.json").write_text("{}", encoding="utf-8")
            chosen = resolve_fnd_profile_path(public_dir=public_dir, fallback_dir=fallback_dir, msn_id="1-2-3")
            self.assertEqual(chosen, fallback_dir / "fnd-1-2-3.json")

    def test_contact_card_optional_fnd_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            public_dir.mkdir(parents=True, exist_ok=True)
            (public_dir / "fnd-1-2-3.json").write_text("{}", encoding="utf-8")
            self.assertIsNone(find_local_contact_card(public_dir=public_dir, fallback_dir=None, msn_id="1-2-3", include_fnd=False))
            with_fnd = find_local_contact_card(public_dir=public_dir, fallback_dir=None, msn_id="1-2-3", include_fnd=True)
            self.assertEqual(with_fnd, public_dir / "fnd-1-2-3.json")


if __name__ == "__main__":
    unittest.main()
