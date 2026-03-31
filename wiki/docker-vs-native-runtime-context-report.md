# Docker Usage vs Native Services on the EC2 Server

## Purpose

This report is a reference document for revisiting the server instability issue and for deciding whether Docker is actually required for the current server architecture.

The immediate practical question was:

- whether Docker is only being used for Keycloak
- whether some or most of the current services can be run without Docker
- whether the recent SSH / VS Code hangs were more likely caused by Docker runtime activity than by VS Code itself

---

## Executive conclusion

Docker is **not** only being used for Keycloak.

There appears to be **one Keycloak service**, but Docker is also being used for:

- Keycloak database
- oauth2-proxy
- Redis
- platform database
- FND portal
- TFF portal
- PayPal proxy
- AWS proxy
- portal auth Redis
- portal auth oauth2-proxy

The services that are easiest and safest to remove from Docker first are the **Python services**:

- `fnd_portal`
- `tff_portal`
- `paypal_proxy`
- `aws_proxy`

Those services are structurally simple Flask + Gunicorn applications and do not appear to require Docker for correctness.

A reasonable long-term architecture is:

- run the Python apps natively with `systemd` + `venv`
- optionally run `oauth2-proxy`, Redis, and Postgres natively as well
- keep Keycloak in Docker initially if desired
- only consider moving Keycloak out of Docker later, after the rest of the stack is stable

The recent SSH / VS Code issue should be treated primarily as a **Docker / container runtime / host-load issue**, not a pure VS Code issue, because plain terminal SSH was hanging too.

---

## Why this conclusion was reached

### 1) The issue was not limited to VS Code

At one point, VS Code Remote-SSH looked like the problem. But later, plain terminal SSH from the local machine also began hanging.

That matters because:

- if VS Code alone were the issue, normal terminal SSH should have remained consistently fine
- once plain SSH also hung, the problem was clearly broader than the VS Code remote agent

The practical implication is that VS Code should be treated as a **symptom surface**, not the root cause.

---

## Current Docker-defined service inventory

### Platform compose stack

From `compose/platform/docker-compose.yml`, Docker is being used for:

- `keycloak_db`
- `oauth2_proxy`
- `redis`
- `keycloak`
- `platform_db`

This means the platform/auth stack currently uses Docker for more than Keycloak alone.

### Portals compose stack

From `compose/portals/docker-compose.yml`, Docker is being used for:

- `fnd_portal`
- `tff_portal`
- `paypal_proxy`
- `aws_proxy`
- `redis_portal` (auth profile)
- `oauth2_proxy_portal` (auth profile)

So Docker is also hosting the portal runtimes and the two small proxy services.

---

## What the repos imply about Docker necessity

### A. Portal runtimes are strong candidates for native systemd services

The portal runtime Dockerfile is very simple:

- base image: `python:3.12-slim`
- install requirements from `runtime/requirements.txt`
- copy runtime files
- run Gunicorn binding to `0.0.0.0:5000`

The runtime requirements are also small:

- Flask
- gunicorn
- cryptography
- python-dotenv

This is the profile of an application that can be run natively very easily using:

- a Python virtual environment
- a working directory
- environment variables
- a `systemd` unit that launches Gunicorn

That means `fnd_portal` and `tff_portal` do **not** need Docker in order to function.

### Practical interpretation

Docker is currently serving mainly as packaging and process management for the portals, not as a hard functional dependency.

---

### B. `aws_proxy` and `paypal_proxy` are even easier to remove from Docker

The `aws_proxy` and `paypal_proxy` Dockerfiles are also minimal:

- base image: `python:3.12-slim`
- install `Flask` and `gunicorn`
- copy `app.py`
- run Gunicorn

The `aws_proxy` app code is ordinary Flask code that:

- reads configuration from environment variables
- writes state to the filesystem
- serves HTTP endpoints
- does not appear to depend on container-only features

That means both proxy services are excellent candidates for native execution under `systemd`.

### Practical interpretation

If the goal is to reduce Docker-related churn quickly, these two proxy services should be among the first to move.

---

### C. Redis and Postgres do not inherently require Docker

Redis and Postgres are being run in Docker today, but neither one inherently depends on containers.

Both can be installed and managed natively on Debian via:

- `apt`
- local config files
- native `systemd` units

Whether they should be moved depends less on technical feasibility and more on operational preference.

### Practical interpretation

They can be moved off Docker, but this is a second-stage cleanup, not the first move.

---

### D. Keycloak can also be run natively, but it should be the last migration

Keycloak is currently defined once, with one associated Postgres database container.

It is reasonable to say:

- yes, there appears to be a single Keycloak service
- no, Docker usage is not limited to Keycloak

Keycloak can run outside Docker, but compared with the Flask services it is:

- heavier
- more configuration-sensitive
- more likely to introduce auth regressions during migration

### Practical interpretation

If Docker reduction is the goal, Keycloak should usually remain containerized until the simpler Python services are already running natively and the host is stable.

---

## Recommended migration priority

### Phase 1 — remove Docker from the Python apps first

Highest-value services to migrate first:

- `fnd_portal`
- `tff_portal`
- `aws_proxy`
- `paypal_proxy`

### Why this phase first

These are the easiest to re-home because they are basically:

- source tree
- Python dependencies
- Gunicorn process
- local files and env vars

This phase removes a meaningful amount of Docker runtime activity while keeping the migration risk comparatively low.

---

### Phase 2 — consider moving auth support and databases off Docker

Possible next candidates:

- `oauth2_proxy`
- `redis`
- `redis_portal`
- `platform_db`
- `keycloak_db`

### Why this phase second

These services can run natively, but they are foundational dependencies. Moving them too early adds operational risk before the Python apps have already been simplified.

---

### Phase 3 — decide whether Keycloak should remain containerized

Final optional migration:

- `keycloak`

### Why this phase last

Keycloak is the least attractive early migration target because auth problems are high-friction and harder to debug than Flask service startup issues.

---

## Architecture recommendation

If the objective is to reduce server strain and simplify debugging on this EC2 instance, the cleanest architecture is likely:

### Keep initially

- Keycloak in Docker, if desired

### Move to native `systemd` + `venv`

- FND portal
- TFF portal
- AWS proxy
- PayPal proxy

### Later decide whether to move natively

- oauth2-proxy
- Redis
- Postgres

This gives a middle path:

- large reduction in container activity
- less bridge/veth/containerd churn
- lower debugging complexity
- smaller migration risk than a full anti-Docker rewrite

---

## Why Docker became a suspect in the stability problem

The practical reasoning from the troubleshooting was:

1. plain terminal SSH began hanging, not just VS Code Remote-SSH
2. stopping Docker and containerd fully resulted in:
   - `docker.service` inactive
   - `docker.socket` inactive
   - `containerd.service` inactive
3. process checks and bound-port checks came back empty after shutdown
4. that means the heavy runtime layer on the host was removed cleanly

This does not prove every failure was caused by Docker, but it does strongly support the conclusion that Docker / container runtime behavior was part of the instability path.

---

## What to remember next time

### Core interpretation

When the server becomes slow or SSH begins hanging:

- do **not** assume it is VS Code first
- first decide whether plain terminal SSH is also affected
- if plain SSH is affected, treat it as a host/service/runtime issue
- Docker/containerd should be considered early in the investigation

### Important distinction

#### If plain terminal SSH is fine, but VS Code hangs

Then the problem may be:

- VS Code Remote-SSH state
- remote `.vscode-server`
- local VS Code Remote-SSH cache

#### If plain terminal SSH also hangs

Then the problem is broader and VS Code is probably not the main issue.

---

## Practical next-time checklist

### 1) Determine whether the issue is VS Code-only or host-wide

Run from the local computer terminal:

```bash
cd ~

ssh -i ~/.ssh/aws-main-key admin@52.70.228.90
```

Interpretation:

- if this is immediate and stable, the host is probably fine
- if this hangs too, do not treat the issue as VS Code-specific

---

### 2) Check runtime services once shell access is recovered

Run on the server from `/`:

```bash
cd /

systemctl is-enabled docker.service docker.socket containerd.service compose-platform.service platform.service
sudo systemctl status docker.service docker.socket containerd.service compose-platform.service platform.service --no-pager
```

This shows both boot posture and live state.

---

### 3) If needed, fully stop Docker and containerd

Run on the server from `/`:

```bash
cd /

sudo systemctl stop docker.service docker.socket containerd.service
sudo systemctl kill docker.service containerd.service || true
sudo systemctl status docker.service docker.socket containerd.service --no-pager
```

---

### 4) Verify the runtime is actually gone

Run on the server from `/`:

```bash
cd /

ps -ef | egrep 'dockerd|containerd|containerd-shim' | grep -v grep
ss -lntp | egrep '(:8081|:9001|:4181|:5101|:5203)'
```

Interpretation:

- ideally no matching processes
- ideally no matching proxy ports
- if they still exist, the runtime stack is not really down yet

---

### 5) Only after SSH is normal again, test VS Code

If plain SSH becomes stable after stopping the runtime, then retry VS Code.

If VS Code alone still hangs after plain SSH is stable, then reset the VS Code remote server state:

Run from the local computer terminal:

```bash
cd ~

ssh -i ~/.ssh/aws-main-key admin@52.70.228.90 '
set -eu
pkill -u admin -f ".vscode-server" || true
rm -rf ~/.vscode-server ~/.vscode-remote
rm -rf /tmp/vscode-ssh-* /tmp/vscode-server-* 2>/dev/null || true
'
```

---

## Suggested long-term direction

The most reasonable long-term simplification path is:

1. retire Docker for the small Python services
2. keep only the services in Docker that clearly justify it
3. re-evaluate whether Keycloak should remain the only containerized app
4. avoid mixing:
   - legacy systemd units
   - multiple overlapping Docker Compose stacks
   - Python services that could run directly

The more the server uses simple native `systemd` services for the Flask/Gunicorn apps, the easier it becomes to answer:

- what is running
- what failed
- what is listening
- what starts on boot
- what can be stopped cleanly

---

## Bottom-line summary

- There is one Keycloak service, but Docker is being used for much more than Keycloak.
- The main candidates to remove from Docker are the Flask/Gunicorn services:
  - `fnd_portal`
  - `tff_portal`
  - `aws_proxy`
  - `paypal_proxy`
- Redis, Postgres, and oauth2-proxy can also be run natively, but are better treated as second-stage migrations.
- Keycloak can also be run natively, but should be the last migration if it is migrated at all.
- The recent hang pattern should be contextualized primarily as a host/runtime problem, not a pure VS Code issue.

---

## Repo references used

- `Fruitful-Network-Development/srv-infra`
  - `compose/platform/docker-compose.yml`
  - `compose/portals/docker-compose.yml`
  - `compose/portals/aws_proxy/Dockerfile`
  - `compose/portals/aws_proxy/requirements.txt`
  - `compose/portals/aws_proxy/app.py`
  - `compose/portals/paypal_proxy/Dockerfile`
  - `compose/portals/paypal_proxy/requirements.txt`

- `Fruitful-Network-Development/mycite-core`
  - `portals/runtime/Dockerfile`
  - `portals/runtime/requirements.txt`
