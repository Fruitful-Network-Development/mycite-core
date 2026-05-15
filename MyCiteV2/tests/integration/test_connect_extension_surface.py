"""Phase 17b — ext_connect extension surface contract.

The new Connect extension joins the subtab strip on
``/portal/utilities/extensions`` as a 5th tab. Its payload exposes:

  * ``configuration`` block with the grantee's ``connect.forward_to_email``
    + a link back to the Grantee Profile.
  * ``submissions`` list filtered to ``source=connect_form`` rows from
    the same newsletter contact log (so leads + subscribers share one
    store, but the renderer split serves the two operator workflows).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
    run_datum_workbench_mutation_action,
)
from MyCiteV2.instances._shared.runtime.utilities_extensions.connect import (
    _build_connect_extension_payload,
)
from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
    MosDatumNewsletterContactLogAdapter,
)


def _build():
    tmp = Path(tempfile.mkdtemp(prefix="phase17b_ext_connect_"))
    for sub in ("private",):
        (tmp / sub).mkdir()
    db = tmp / "authority.sqlite3"
    db.touch()
    return tmp / "private", db


class ConnectExtensionConfigurationTests(unittest.TestCase):
    def test_configuration_carries_forward_to_email(self) -> None:
        private_dir, _ = _build()
        out = _build_connect_extension_payload(
            grantee={
                "msn_id": "fnd",
                "connect": {"forward_to_email": "dylan@fruitfulnetworkdevelopment.com"},
            },
            domain="fruitfulnetworkdevelopment.com",
            private_dir=private_dir,
        )
        self.assertEqual(out["forward_to_email"], "dylan@fruitfulnetworkdevelopment.com")
        items = out["configuration"]["items"]
        self.assertTrue(any(
            item["label"] == "Forward-to email"
            and "dylan@" in item["value"]
            for item in items
        ))

    def test_configuration_warns_when_forward_unset(self) -> None:
        private_dir, _ = _build()
        out = _build_connect_extension_payload(
            grantee={"msn_id": "fnd"},
            domain="fruitfulnetworkdevelopment.com",
            private_dir=private_dir,
        )
        self.assertEqual(out["forward_to_email"], "")
        self.assertIn("Configure ``connect.forward_to_email``", out.get("notice") or "")


class ConnectExtensionSubmissionsFilterTests(unittest.TestCase):
    def test_only_connect_form_rows_surface(self) -> None:
        private_dir, db = _build()
        # Two newsletter subscribers + two connect-form submissions.
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "upsert_subscriber",
                "domain": "example.test",
                "email": "subscriber-1@example.test",
                "first_name": "Sub",
            },
            authority_db_file=db,
            portal_instance_id="fnd",
        )
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "upsert_subscriber",
                "domain": "example.test",
                "email": "subscriber-2@example.test",
                "first_name": "Two",
            },
            authority_db_file=db,
            portal_instance_id="fnd",
        )
        for visitor_email, subject in (
            ("connect-1@example.test", "First question"),
            ("connect-2@example.test", "Second question"),
        ):
            run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "aws_csm_newsletter_contact_log",
                    "operation": "submit_connect_form",
                    "domain": "example.test",
                    "email": visitor_email,
                    "first_name": "Visitor",
                    "subject": subject,
                    "message": "Body",
                    "forward_status": "sent",
                },
                authority_db_file=db,
                portal_instance_id="fnd",
            )

        out = _build_connect_extension_payload(
            grantee={"msn_id": "fnd", "domains": ["example.test"]},
            domain="example.test",
            private_dir=private_dir,
            authority_db_file=db,
        )
        emails = {s["email"] for s in out["submissions"]}
        self.assertEqual(
            emails, {"connect-1@example.test", "connect-2@example.test"}
        )
        # Newsletter-only subscribers must NOT appear in submissions.
        self.assertNotIn("subscriber-1@example.test", emails)
        self.assertNotIn("subscriber-2@example.test", emails)
        self.assertEqual(out["submission_count"], 2)

    def test_submission_rows_carry_subject_message_forward_status(self) -> None:
        private_dir, db = _build()
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "submit_connect_form",
                "domain": "example.test",
                "email": "lead@example.test",
                "first_name": "Lead",
                "last_name": "Person",
                "subject": "Pricing?",
                "message": "What does an annual plan cost?",
                "forward_status": "sent",
            },
            authority_db_file=db,
            portal_instance_id="fnd",
        )
        out = _build_connect_extension_payload(
            grantee={"msn_id": "fnd", "domains": ["example.test"]},
            domain="example.test",
            private_dir=private_dir,
            authority_db_file=db,
        )
        row = out["submissions"][0]
        self.assertEqual(row["email"], "lead@example.test")
        self.assertEqual(row["subject"], "Pricing?")
        self.assertEqual(row["message"], "What does an annual plan cost?")
        self.assertEqual(row["forward_status"], "sent")
        self.assertFalse(row["subscribed_to_newsletter"])
        self.assertEqual(row["name"], "Lead Person")


class ConnectExtensionRegistrationTests(unittest.TestCase):
    def test_ext_connect_is_in_renderer_dispatch(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            EXTENSION_RENDERERS,
        )

        self.assertIn("ext_connect", EXTENSION_RENDERERS)

    def test_ext_connect_is_in_subtab_order(self) -> None:
        from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
            _OPERATIONAL_EXTENSION_ORDER,
        )

        self.assertIn("ext_connect", _OPERATIONAL_EXTENSION_ORDER)
        # 5 tabs total now.
        self.assertEqual(len(_OPERATIONAL_EXTENSION_ORDER), 5)


if __name__ == "__main__":
    unittest.main()
