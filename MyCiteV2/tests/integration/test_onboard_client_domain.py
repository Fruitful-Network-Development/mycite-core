"""C4 — one-shot client-domain onboarding orchestrator.

Pins:
  * Dry-run executes NONE of the adapter methods and reports status=dry_run
    for every step.
  * Apply calls all 4 adapter methods in order with the right args (tags
    derived from --tenant).
  * A failure in one step is reported but does not abort the others.
  * main() returns non-zero exit when any step errors, zero otherwise.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.scripts import onboard_client_domain as ocd


class OnboardDryRunTests(unittest.TestCase):
    def test_dry_run_touches_nothing(self) -> None:
        adapter = MagicMock()
        steps = ocd.run_onboarding(
            domain="example.org", tenant="acme", dry_run=True, adapter=adapter
        )
        # No adapter method called.
        adapter.ensure_domain_identity.assert_not_called()
        adapter.sync_domain_dns.assert_not_called()
        adapter.ensure_domain_receipt_rule.assert_not_called()
        adapter.sync_operator_forwarding_routes.assert_not_called()
        # Every step reported dry_run.
        self.assertEqual([s["status"] for s in steps], ["dry_run"] * 4)
        self.assertEqual(
            [s["step"] for s in steps],
            [
                "ensure_domain_identity",
                "sync_domain_dns",
                "ensure_domain_receipt_rule",
                "sync_operator_forwarding_routes",
            ],
        )


class OnboardApplyTests(unittest.TestCase):
    def _ok_adapter(self) -> MagicMock:
        adapter = MagicMock()
        adapter.ensure_domain_identity.return_value = {"ok": True}
        adapter.sync_domain_dns.return_value = {"ok": True}
        adapter.ensure_domain_receipt_rule.return_value = {"ok": True}
        adapter.sync_operator_forwarding_routes.return_value = {"status": "ok"}
        return adapter

    def test_apply_calls_all_steps_in_order_with_tags(self) -> None:
        adapter = self._ok_adapter()
        steps = ocd.run_onboarding(
            domain="example.org", tenant="acme", dry_run=False, adapter=adapter
        )
        self.assertEqual([s["status"] for s in steps], ["ok"] * 4)
        adapter.ensure_domain_identity.assert_called_once_with(
            "example.org", tags={"tenant": "acme"}
        )
        adapter.sync_domain_dns.assert_called_once_with(
            "example.org", tags={"tenant": "acme"}
        )
        adapter.ensure_domain_receipt_rule.assert_called_once_with(
            "example.org", tags={"tenant": "acme"}
        )
        adapter.sync_operator_forwarding_routes.assert_called_once_with(dry_run=False)

    def test_no_tenant_passes_none_tags(self) -> None:
        adapter = self._ok_adapter()
        ocd.run_onboarding(
            domain="example.org", tenant="", dry_run=False, adapter=adapter
        )
        adapter.ensure_domain_identity.assert_called_once_with(
            "example.org", tags=None
        )

    def test_one_step_error_does_not_abort_the_rest(self) -> None:
        adapter = self._ok_adapter()
        adapter.sync_domain_dns.side_effect = RuntimeError("hosted_zone_missing")
        steps = ocd.run_onboarding(
            domain="example.org", tenant="acme", dry_run=False, adapter=adapter
        )
        status_by_step = {s["step"]: s["status"] for s in steps}
        self.assertEqual(status_by_step["ensure_domain_identity"], "ok")
        self.assertEqual(status_by_step["sync_domain_dns"], "error")
        # downstream steps still ran
        self.assertEqual(status_by_step["ensure_domain_receipt_rule"], "ok")
        self.assertEqual(status_by_step["sync_operator_forwarding_routes"], "ok")

    def test_step_returning_ok_false_marked_failed(self) -> None:
        adapter = self._ok_adapter()
        adapter.ensure_domain_receipt_rule.return_value = {"ok": False, "error": "x"}
        steps = ocd.run_onboarding(
            domain="example.org", tenant="acme", dry_run=False, adapter=adapter
        )
        status_by_step = {s["step"]: s["status"] for s in steps}
        self.assertEqual(status_by_step["ensure_domain_receipt_rule"], "failed")


class OnboardMainExitCodeTests(unittest.TestCase):
    def test_dry_run_main_exit_zero(self) -> None:
        from unittest.mock import patch
        with patch.object(ocd, "run_onboarding", return_value=[
            {"step": "x", "status": "dry_run", "detail": ""},
        ]):
            rc = ocd.main(["--domain", "example.org", "--dry-run"])
        self.assertEqual(rc, 0)

    def test_main_exit_nonzero_on_error(self) -> None:
        from unittest.mock import patch
        with patch.object(ocd, "run_onboarding", return_value=[
            {"step": "sync_domain_dns", "status": "error", "detail": "boom"},
        ]):
            rc = ocd.main(["--domain", "example.org", "--apply"])
        self.assertEqual(rc, 1)

    def test_requires_apply_or_dry_run(self) -> None:
        with self.assertRaises(SystemExit):
            ocd.main(["--domain", "example.org"])


if __name__ == "__main__":
    unittest.main()
