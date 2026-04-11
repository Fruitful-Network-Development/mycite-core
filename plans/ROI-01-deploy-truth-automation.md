# ROI 01 — Deploy-Truth Automation

## Objective

Create a repeatable deploy-truth check that proves whether the live portal is serving the intended V2 revision, static assets, and upstream routing.

## Why this is high ROI

Recent portal work repeatedly converged in repo state while remaining unresolved on the live host. The current repo now contains explicit build markers, shell-template markers, and static-bundle health checks, but those only help if they are used in a repeatable operational check.

This area yields high return because it prevents the same failure mode from recurring:

- repo fixed, live stale
- repo fixed, nginx wrong
- HTML updated, CSS missing
- tests passing, live behavior still broken

## Scope

Primary files and surfaces:

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/portal_host/templates/portal.html`
- `srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`
- live host nginx config
- live systemd unit or service serving the portal

## Deliverables

1. A repeatable verification script or documented command sequence.
2. A short deploy checklist for portal releases.
3. A report format that captures repo, host, and live truth separately.
4. A required post-deploy smoke run.

## Definition of done

This ROI area is complete when all of the following are true:

- there is a standard command sequence that checks repo markers, host config, and live HTTP evidence
- the command sequence is stored in the repo in a stable location
- a release cannot be called complete without running those checks
- command output is preserved in a verification report

## Suggested implementation shape

- Add a small script under a stable ops location, for example:
  - `MyCiteV2/scripts/verify_portal_live.sh`
  - or `ops/verify_portal_live.sh`
- Include checks for:
  - `/portal/system` shell marker and build marker
  - `/portal/static/portal.css` 200
  - `/portal/static/v2_portal_shell.js` 200
  - `/healthz` static bundle state
  - actual nginx config path in use
  - actual running service/unit and revision/build marker

## Task classification

`repo_and_deploy`

## Agent execution plan

### Lead

- open a new task for deploy-truth automation
- mark it `repo_and_deploy`
- list both repo and host acceptance criteria
- require verifier closure

### Implementer

- add the script or documented command entrypoint
- update repo docs so deploy completion requires the script
- if allowed, install or run the script on the host after deploy
- record exact outputs

### Verifier

- run the same script or same commands independently
- compare output against acceptance criteria
- fail the task if any layer is missing or inconsistent

## Required evidence pattern

- Repo findings
- Host findings
- Live findings
- Final verdict

## Starter commands

```bash
cd /tmp
curl -s https://portal.fruitfulnetworkdevelopment.com/portal/system | grep -n "shell-template: v2-composition\|build:"
curl -I https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css
curl -I https://portal.fruitfulnetworkdevelopment.com/portal/static/v2_portal_shell.js
curl -s https://portal.fruitfulnetworkdevelopment.com/healthz | python3 -m json.tool
```
