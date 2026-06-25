"""Secret-masking helper for the utilities extensions.

The per-extension ``configuration`` payload builders (paypal / email /
newsletter / analytics) and the ``_grantee_edit_link`` metadata block were
removed when the FND-CSM operator surface was dissolved. The remaining
shared helper exercised here is ``_mask_secret`` — the redaction used so
plaintext client_secret / smtp_password never crosses a surface payload.

Tests:
  - Secret-masking helper redacts long secrets, masks short ones entirely
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import (
    _mask_secret,
)


class SecretMaskingTests(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(_mask_secret(""), "")
        self.assertEqual(_mask_secret(None), "")

    def test_short_secret_fully_masked(self) -> None:
        masked = _mask_secret("abc")
        self.assertEqual(masked, "•••")

    def test_long_secret_keeps_last_four(self) -> None:
        masked = _mask_secret("abcdef123456")
        self.assertTrue(masked.endswith("3456"))
        self.assertEqual(len(masked), len("abcdef123456"))


if __name__ == "__main__":
    unittest.main()
