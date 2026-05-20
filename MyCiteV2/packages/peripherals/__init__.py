"""Peripherals — external-integration packages.

Each subpackage under `peripherals/` is one external surface (currently
only `aws/`; future siblings: `oauth/`, `payments/`, etc.). A peripheral
package is self-contained: it does not import from other peripherals,
does not depend on MOS database state, and is consumed by extensions
(`MyCiteV2/instances/_shared/runtime/utilities_extensions/*.py`) through
its public Protocol.
"""
