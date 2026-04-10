"""AWS narrow-write semantic owner for the Admin Band 2 write slice."""

from .service import (
    ALLOWED_AWS_NARROW_WRITE_FIELDS,
    AwsNarrowWriteCommand,
    AwsNarrowWriteOutcome,
    AwsNarrowWriteService,
    normalize_aws_narrow_write_command,
)

__all__ = [
    "ALLOWED_AWS_NARROW_WRITE_FIELDS",
    "AwsNarrowWriteCommand",
    "AwsNarrowWriteOutcome",
    "AwsNarrowWriteService",
    "normalize_aws_narrow_write_command",
]
