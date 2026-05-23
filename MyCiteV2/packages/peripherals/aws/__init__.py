"""AWS peripheral — the single connector package the rest of the codebase
uses to talk to AWS (Lambda, SES, Route53, SecretsManager, S3).

Public surface:

* `AwsPeripheralPort` — the Protocol every consumer programs against.
* `AwsPeripheralCloudAdapter` — production boto3 implementation; satisfies
  the Protocol.
* `ProfileStore` — operator profile JSON reader. Only authorized reader
  for the peripheral; no MOS, no SQL.

Extensions (e.g. `utilities_extensions/email.py`,
`utilities_extensions/newsletter.py`, future `tooling.py`) should
import from this module — never reach into legacy adapter
directly.

CLI entrypoint: `python -m MyCiteV2.packages.peripherals.aws.cli ...`
"""

from __future__ import annotations

from .cloud_adapter import AwsPeripheralCloudAdapter
from .contracts import (
    AwsEvidence,
    AwsPeripheralPort,
    CostBreakdown,
    CostLineItem,
    DomainStatus,
    ForwardingRoutesSyncResult,
    ProfileReadiness,
)
from .probe_cache import ProbeCache
from .profile_store import ProfileStore, iter_profile_recipient_targets


__all__ = [
    "AwsEvidence",
    "AwsPeripheralCloudAdapter",
    "AwsPeripheralPort",
    "CostBreakdown",
    "CostLineItem",
    "DomainStatus",
    "ForwardingRoutesSyncResult",
    "ProbeCache",
    "ProfileReadiness",
    "ProfileStore",
    "iter_profile_recipient_targets",
]
