from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResourceProvenance:
    source_msn_id: str
    resource_id: str
    export_family: str
    wire_variant: str
    source_href: str
    fetched_unix_ms: int
    payload_sha256: str
    source_card_revision: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_msn_id": self.source_msn_id,
            "resource_id": self.resource_id,
            "export_family": self.export_family,
            "wire_variant": self.wire_variant,
            "source_href": self.source_href,
            "fetched_unix_ms": self.fetched_unix_ms,
            "payload_sha256": self.payload_sha256,
            "source_card_revision": self.source_card_revision,
        }
