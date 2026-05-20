"""Unit tests for the tolling-prerequisite surface on
`AwsPeripheralCloudAdapter`: tag_resource + get_costs_by_grantee +
get_costs_overview. Mocked at the boto3 boundary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.peripherals.aws.cloud_adapter import AwsPeripheralCloudAdapter


class _StubTaggingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.next_response: dict[str, Any] = {"FailedResourcesMap": {}}

    def tag_resources(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.next_response


class _StubCostExplorer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.next_response: dict[str, Any] = {"ResultsByTime": []}

    def get_cost_and_usage(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.next_response


class TagResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
        self.tagging = _StubTaggingClient()
        self.adapter._cached_clients["resourcegroupstaggingapi@us-east-1"] = self.tagging

    def test_tags_one_resource(self) -> None:
        arn = "arn:aws:ses:us-east-1:065948377733:configuration-set/fnd-default"
        result = self.adapter.tag_resource(
            arns=[arn], tags={"msn_id": "abc", "tenant": "fnd"}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["tagged_arns"], [arn])
        self.assertEqual(result["failed_arns"], [])
        call = self.tagging.calls[0]
        self.assertEqual(call["ResourceARNList"], [arn])
        self.assertEqual(call["Tags"], {"msn_id": "abc", "tenant": "fnd"})

    def test_reports_per_resource_failures(self) -> None:
        arn_ok = "arn:aws:s3:::ses-inbound-fnd-mail"
        arn_bad = "arn:aws:lambda:us-east-1:065948377733:function:does-not-exist"
        self.tagging.next_response = {
            "FailedResourcesMap": {
                arn_bad: {
                    "ErrorCode": "InvalidParameterException",
                    "ErrorMessage": "Function not found",
                }
            }
        }
        result = self.adapter.tag_resource(
            arns=[arn_ok, arn_bad], tags={"msn_id": "abc"}
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["tagged_arns"], [arn_ok])
        self.assertEqual(len(result["failed_arns"]), 1)
        self.assertEqual(result["failed_arns"][0]["arn"], arn_bad)
        self.assertEqual(result["failed_arns"][0]["error_code"], "InvalidParameterException")

    def test_empty_arns_is_noop(self) -> None:
        result = self.adapter.tag_resource(arns=[], tags={"msn_id": "abc"})
        self.assertTrue(result["ok"])
        self.assertEqual(self.tagging.calls, [])

    def test_empty_tags_returns_failure_without_calling_aws(self) -> None:
        result = self.adapter.tag_resource(arns=["arn:aws:s3:::foo"], tags={})
        self.assertFalse(result["ok"])
        self.assertEqual(self.tagging.calls, [])
        self.assertEqual(len(result["failed_arns"]), 1)
        self.assertEqual(result["failed_arns"][0]["error_code"], "EmptyTags")


class CostExplorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
        self.ce = _StubCostExplorer()
        self.adapter._cached_clients["ce@us-east-1"] = self.ce

    def test_get_costs_by_grantee_filters_and_groups(self) -> None:
        self.ce.next_response = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-04-01", "End": "2026-05-01"},
                    "Groups": [
                        {
                            "Keys": ["Amazon Simple Email Service"],
                            "Metrics": {"UnblendedCost": {"Amount": "1.25", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["Amazon Route 53"],
                            "Metrics": {"UnblendedCost": {"Amount": "0.50", "Unit": "USD"}},
                        },
                    ],
                }
            ]
        }
        result = self.adapter.get_costs_by_grantee(
            msn_id="3-2-3-17-77-1-6-4-1-4",
            start="2026-04-01",
            end="2026-05-01",
        )
        # Filter shape: Tags filter with Key=msn_id, Values=[msn_id]
        call = self.ce.calls[0]
        self.assertEqual(
            call["Filter"],
            {"Tags": {"Key": "msn_id", "Values": ["3-2-3-17-77-1-6-4-1-4"]}},
        )
        self.assertEqual(call["GroupBy"], [{"Type": "DIMENSION", "Key": "SERVICE"}])
        self.assertEqual(call["Metrics"], ["UnblendedCost"])
        self.assertEqual(call["Granularity"], "MONTHLY")
        # Result shape
        self.assertEqual(result["currency"], "USD")
        self.assertAlmostEqual(float(result["grand_total"]), 1.75, places=4)
        self.assertEqual(set(result["by_service"].keys()),
                         {"Amazon Simple Email Service", "Amazon Route 53"})
        self.assertAlmostEqual(float(result["by_service"]["Amazon Simple Email Service"]), 1.25)
        self.assertEqual(result["period_start"], "2026-04-01")
        self.assertEqual(result["period_end"], "2026-05-01")

    def test_get_costs_by_grantee_sums_across_periods(self) -> None:
        self.ce.next_response = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["A"], "Metrics": {"UnblendedCost": {"Amount": "1.00", "Unit": "USD"}}},
                    ],
                },
                {
                    "Groups": [
                        {"Keys": ["A"], "Metrics": {"UnblendedCost": {"Amount": "2.00", "Unit": "USD"}}},
                    ],
                },
            ]
        }
        result = self.adapter.get_costs_by_grantee(
            msn_id="abc", start="2026-01-01", end="2026-03-01", granularity="MONTHLY"
        )
        self.assertAlmostEqual(float(result["by_service"]["A"]), 3.00)
        self.assertAlmostEqual(float(result["grand_total"]), 3.00)

    def test_get_costs_overview_groups_by_tag_and_service(self) -> None:
        self.ce.next_response = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["msn_id$abc", "Amazon Simple Email Service"],
                            "Metrics": {"UnblendedCost": {"Amount": "1.00", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["msn_id$def", "Amazon Simple Email Service"],
                            "Metrics": {"UnblendedCost": {"Amount": "0.40", "Unit": "USD"}},
                        },
                        {
                            "Keys": ["msn_id$abc", "Amazon Route 53"],
                            "Metrics": {"UnblendedCost": {"Amount": "0.50", "Unit": "USD"}},
                        },
                        {
                            # Un-tagged remainder.
                            "Keys": ["msn_id$", "Amazon S3"],
                            "Metrics": {"UnblendedCost": {"Amount": "0.15", "Unit": "USD"}},
                        },
                    ],
                }
            ]
        }
        result = self.adapter.get_costs_overview(
            start="2026-04-01", end="2026-05-01"
        )
        self.assertEqual(set(result.keys()), {"abc", "def", ""})
        self.assertAlmostEqual(float(result["abc"]["grand_total"]), 1.50)
        self.assertEqual(set(result["abc"]["by_service"].keys()),
                         {"Amazon Simple Email Service", "Amazon Route 53"})
        self.assertAlmostEqual(float(result["def"]["by_service"]["Amazon Simple Email Service"]), 0.40)
        self.assertAlmostEqual(float(result[""]["by_service"]["Amazon S3"]), 0.15)
        # Request shape: two-dim GroupBy [Tag:msn_id, Dimension:SERVICE]
        call = self.ce.calls[0]
        self.assertEqual(call["GroupBy"], [
            {"Type": "TAG", "Key": "msn_id"},
            {"Type": "DIMENSION", "Key": "SERVICE"},
        ])
        # No Filter on overview — we want every grantee in one shot.
        self.assertNotIn("Filter", call)


if __name__ == "__main__":
    unittest.main()
