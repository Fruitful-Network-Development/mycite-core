"""Orchestration seam for staged AWS-CSM profile artifacts (ADR 0006).

Semantic mapping and IO remain in modules and adapters; this package only
validates that a caller-supplied path is a readable live-profile document
before runtime hands it to ``FilesystemLiveAwsProfileAdapter``.
"""

from __future__ import annotations

from pathlib import Path

from MyCiteV2.packages.adapters.filesystem import is_live_aws_profile_file


def validate_staged_aws_csm_profile_path(path: str | Path) -> Path:
    """Fail closed unless ``path`` is a valid ``mycite.service_tool.aws_csm.profile.v1`` file."""
    resolved = Path(path)
    if not resolved.is_file():
        raise ValueError("sandbox aws csm profile path is not a readable file")
    if not is_live_aws_profile_file(resolved):
        raise ValueError(
            "sandbox aws csm profile must be a valid mycite.service_tool.aws_csm.profile.v1 document"
        )
    return resolved
