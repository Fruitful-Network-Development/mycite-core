# mycite-le_fnd

Portal instance directory in `mycite-core`.

## Role

- Active app runtime (`app.py` present).
- Uses shared service-shell/tool-runtime conventions from `portals/_shared`.
- Footer includes account/portal hub with `Switch User`, remembered account selector, and portal availability list.

## Local run

```bash
cd /srv/repo/mycite-core/portals/mycite-le_fnd
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Deployment note

This directory is source-of-truth code. `compose/portals` builds directly from this repository path.

Runtime state lives under `/srv/compose/portals/state/<portal_instance>/`.

Do not patch code under running containers; rebuild the target portal service from `/srv/compose/portals` after updates.

## Canonical docs

- [mycite-core root](../../README.md)
- [Service Shell Standard](../../docs/TOOLS_SHELL.md)
- [Development Plan](../../docs/DEVELOPMENT_PLAN.md)
- [AWS Emailer Abstraction](../../docs/AWS_EMAILER_ABSTRACTION.md)
- [PayPal Payment Abstraction](../../docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
- [Request Log and Contracts](../../docs/request_log_and_contracts.md)
- [Documentation Policy](../../docs/DOCUMENTATION_POLICY.md)
