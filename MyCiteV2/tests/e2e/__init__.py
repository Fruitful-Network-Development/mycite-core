"""Browser end-to-end (e2e) test harness for the MyCite portal.

This package boots the real portal Flask app (``create_app``) against the
live fnd MOS authority DB on an ephemeral localhost port and drives it with
Playwright. It is the canonical UI-verification path future tool/lens PRs
should extend.

See ``README.md`` in this directory for setup + the install recipe.
"""
