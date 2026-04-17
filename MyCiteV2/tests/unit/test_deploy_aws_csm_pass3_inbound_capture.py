from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.scripts.deploy_aws_csm_pass3_inbound_capture import (  # noqa: E402
    _build_route_map,
    _updated_rule,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class DeployAwsCsmPass3InboundCaptureTests(unittest.TestCase):
    def test_build_route_map_reads_send_as_and_forward_targets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(
                root / "aws-csm.tff.mark.json",
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.tff.mark",
                        "domain": "trappfamilyfarm.com",
                        "send_as_email": "mark@trappfamilyfarm.com",
                    },
                    "smtp": {
                        "forward_to_email": "trapp.family.farm@gmail.com",
                    },
                },
            )
            _write_json(
                root / "aws-csm.invalid.json",
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {"profile_id": "aws-csm.invalid", "send_as_email": "not-an-email"},
                    "smtp": {"forward_to_email": "also-invalid"},
                },
            )

            routes = _build_route_map(root)

        self.assertEqual(
            routes,
            {
                "mark@trappfamilyfarm.com": {
                    "forward_to_email": "trapp.family.farm@gmail.com",
                    "profile_id": "aws-csm.tff.mark",
                    "domain": "trappfamilyfarm.com",
                }
            },
        )

    def test_updated_rule_replaces_legacy_forwarder_and_normalizes_fnd_prefix(self) -> None:
        updated = _updated_rule(
            {
                "Name": "mode-a-forward-dcmontgomery",
                "Enabled": True,
                "TlsPolicy": "Optional",
                "Recipients": ["fruitfulnetworkdevelopment.com"],
                "Actions": [
                    {
                        "S3Action": {
                            "BucketName": "ses-inbound-fnd-mail",
                            "ObjectKeyPrefix": "inbound/",
                        }
                    },
                    {
                        "LambdaAction": {
                            "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:ses-forwarder",
                            "InvocationType": "Event",
                        }
                    },
                ],
                "ScanEnabled": True,
            },
            function_arn="arn:aws:lambda:us-east-1:123456789012:function:newsletter-inbound-capture",
        )

        self.assertEqual(updated["Actions"][0]["S3Action"]["ObjectKeyPrefix"], "inbound/fruitfulnetworkdevelopment.com/")
        self.assertEqual(
            updated["Actions"][1]["LambdaAction"]["FunctionArn"],
            "arn:aws:lambda:us-east-1:123456789012:function:newsletter-inbound-capture",
        )


if __name__ == "__main__":
    unittest.main()
