# IWMS Government Backend — Deployment Guide

Full flow: local setup → Docker build → server install → GitHub Actions.
Backend runs on **port 9001** internally.

Branch policy: `sathya`/`lux`/`sameer`/`vinoth` (personal) → `dev`
(integration, tests only) → `main` (production, tests + build + deploy).

Public URL once nginx is set up: `http://115.245.93.26/api/v1/` — no port
needed. Until then, directly: `http://115.245.93.26:9001`.

**nginx** sits in front of both this repo's container and the frontend's,
reverse-proxying `/api/`, `/admin/` here and everything else to the
frontend. It's configured once, from the **frontend repo** (nginx is a
single shared host-level thing, not per-repo) — see
[iwms-government-frontend/DEPLOYMENT.md](../iwms-government-frontend/DEPLOYMENT.md)
§5 for the full setup (including disabling Apache, which was confirmed to
be running only the stock default page — nothing real depends on it).

---

## 0. From scratch: get the code onto the server + the deploy key

Do this once, on the **server** (`115.245.93.26`), before anything else in
this doc.

### 0.1 Clone the repo
```bash
sudo mkdir -p /home/admin/localserver/iwmsGovernment
sudo chown -R admin:admin /home/admin/localserver/iwmsGovernment
cd /home/admin/localserver/iwmsGovernment

git clone https://github.com/ZigmaSoftware/iwms-government-backend.git
cd iwms-government-backend
git checkout main
```
This is what `deploy/`, `Dockerfile`, `docker-compose.production.yml` etc.
below refer to as "this repo" on the server — the same files as your local
clone, just checked out here too so `docker compose` and the systemd unit
have something to run from.

### 0.2 Generate the GitHub Actions deploy key — ON THE SERVER
This key is what lets GitHub Actions SSH into this machine later, in
Section 4. Generate it here (not on your laptop), so the public half never
has to travel anywhere:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/gov_deploy_key -C "github-actions-deploy" -N ""

cat ~/.ssh/gov_deploy_key.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh

cat ~/.ssh/gov_deploy_key       # copy this ENTIRE output, BEGIN/END lines included
```
Keep that private-key text — you'll paste it into a GitHub Secret in
Section 4, Step 1. It's the same key for both the backend and frontend
repos, since both deploy to this one server.

---

## 1. What's in this repo for deployment

| File | Purpose |
|---|---|
| `Dockerfile` | Python 3.12 + gunicorn image, binds `0.0.0.0:9001` |
| `.dockerignore` | Keeps venv/media out of the image |
| `docker-compose.production.yml` | Runs the built image, points `backend` at the real database via `.env`. Used on the server. |
| `.github/workflows/deploy.yml` | CI/CD: test → build & push image → deploy |
| `deploy/systemd/iwms-government-backend.service` | Server-only unit file (gitignored, not pushed to GitHub) |

---

## 1a. Nightly trip scheduler — the app schedules itself, no cron needed

There is **no cron job** in this image, and none is needed. The nightly
`generate_daily_trips` job is scheduled **inside the Django app itself**:

- **What runs it:** `app/services/daily_trip_scheduler.py` — a background
  thread started automatically by `AppConfig.ready()`
  ([app/apps.py](app/apps.py)) the moment Django starts. It wakes up,
  checks the configured run time, and calls
  `generate_daily_trips` when due.
- **When:** `04:00` by default. Configurable two ways: a DB-backed
  `SchedulerConfig` singleton row (if present, takes priority — can be
  changed live, no restart needed), or the `DAILY_TRIP_SCHEDULER_TIME` env
  var as a fallback (`HH:MM`). Disable entirely with
  `ENABLE_DAILY_TRIP_JOB_SCHEDULER=false`.
- **Why it's safe with 3 gunicorn workers:** each worker starts its own
  copy of this thread, but `run_daily_trip_job` takes a MySQL
  `GET_LOCK`/`RELEASE_LOCK` before running, keyed by date — so only one
  worker actually executes the job even though all three "wake up" for it.
- **Deliberately does NOT start** for management commands
  (`migrate`, `seed`, `generate_daily_trips` itself, etc.) — only for the
  actual running server process, so `docker compose exec backend python
  manage.py migrate` never accidentally triggers it.
- **Logs:** goes through the normal Python `logging` module → container
  stdout/stderr → `docker compose logs backend`, same place as every other
  Django/gunicorn log line.
- **Manual run / testing a specific date** (unrelated to the scheduler
  thread — this just calls the management command directly):
  ```bash
  docker compose -f docker-compose.production.yml exec backend python manage.py generate_daily_trips
  docker compose -f docker-compose.production.yml exec backend python manage.py generate_daily_trips --date 2026-06-26
  ```

### Migration status
Both `scheduler.sh` (the old host-cron script) and a short-lived
container-cron attempt have been removed from this repo. Neither is
needed — the in-process scheduler above is the single, authoritative
mechanism. If the **server** still has an old host crontab entry calling
`scheduler.sh`, remove it:
```bash
crontab -l          # remove any leftover line calling scheduler.sh, if present
crontab -e
```

---

## 2. Install prerequisites (server, one-time)

```bash
# Docker + Compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker          # or log out/in

docker --version
docker compose version
```

Create the deploy directory and drop a production `.env` there (same keys
as this repo's `.env`, real values — never commit it):

```bash
sudo mkdir -p /home/admin/localserver/iwmsGovernment/iwms-government-backend
sudo chown -R admin:admin /home/admin/localserver/iwmsGovernment
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
nano .env        # paste production values
```

Copy this repo's `docker-compose.production.yml` into that same folder.

Allow Docker to pull from GHCR (either make the package public, or):
```bash
echo <YOUR_GITHUB_PAT> | docker login ghcr.io -u <github-username> --password-stdin
```

Open the firewall port:
```bash
sudo ufw allow 9001/tcp
sudo ufw reload
```

Install the systemd unit (kept locally in `deploy/systemd/`, gitignored —
copy it yourself, it's never pushed):
```bash
sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable iwms-government-backend.service
```

Disable the old cron-based sync so it doesn't fight with the new pipeline:
```bash
crontab -l           # look for backend_sync.sh, remove that line
crontab -e
```

---

## 3. The git branch workflow that drives deployment

This repo's branches form a chain, and `.github/workflows/deploy.yml` only
reacts to two of them:

```
sathya / lux / sameer / vinoth   (personal branches — push here freely)
              │  open a PR
              ▼
             dev          (integration branch)
              │            → push/merge here triggers the "test" job ONLY
              │              (pytest). No image is built, nothing touches
              │              the server. This is where the team catches
              │              breakage before it goes further.
              │  open a PR, once dev is stable
              ▼
             main         (production)
                            → push/merge here triggers ALL three jobs:
                              test → build-and-push → deploy.
                              This is the ONLY branch that ever reaches
                              the server.
```

Pushing to a personal branch never runs anything — the workflow's `on:
push: branches: [dev, main]` doesn't match it. This is deliberate: nothing
in your own in-progress branch can accidentally deploy.

### Step 1 — Add repo secrets (once, before the first deploy)
GitHub repo → Settings → Secrets and variables → Actions → New repository
secret — using the key generated on the server in **Section 0.2**:
- `SERVER_HOST` = `115.245.93.26`
- `SERVER_USER` = `admin`
- `SERVER_SSH_KEY` = the private key text from `cat ~/.ssh/gov_deploy_key`

### Step 2 — Push to `dev` first (safe — no deploy happens)
```bash
git checkout dev
git merge sathya          # or open a PR on GitHub instead of merging locally
git push origin dev
```
Go to the GitHub repo's **Actions** tab → confirm the `test` job runs and
passes. No `build-and-push` or `deploy` job should appear for `dev` — if
one does, something is misconfigured in `deploy.yml`'s `if:` conditions.

### Step 3 — Push to `main` (this actually deploys)
```bash
git checkout main
git merge dev              # or open a PR: dev -> main, then merge on GitHub
git push origin main
```
In the **Actions** tab, confirm all three jobs run in order and go green:
`test` → `build-and-push` → `deploy`.

### Step 4 — Verify on the server
```bash
sudo systemctl status iwms-government-backend.service
docker compose -f /home/admin/localserver/iwmsGovernment/iwms-government-backend/docker-compose.production.yml logs -f backend
curl -i http://127.0.0.1:9001/
curl -i http://115.245.93.26:9001/     # from your own machine, over the network
```
✅ Expect: the container is `Up`, logs show gunicorn serving requests, and
both curl commands return a response.

---

## 4. Manual deploy (bypassing Actions, if ever needed)

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml logs -f backend
docker image prune -f
```

## 5. Rollback

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
docker compose -f docker-compose.production.yml down
docker pull ghcr.io/zigmasoftware/iwms-government-backend:<previous-commit-sha>
# edit docker-compose.production.yml's image tag to that sha, then:
docker compose -f docker-compose.production.yml up -d
```

## 6. Quick troubleshooting

| Symptom | Check |
|---|---|
| `docker compose pull` fails | `docker login ghcr.io` again, or package visibility |
| Container exits immediately | `docker compose logs backend` — usually a missing `.env` value |
| `curl` connection refused | `sudo ufw status`, `systemctl status iwms-government-backend.service` |
| Actions `deploy` job fails at SSH step | Confirm `SERVER_SSH_KEY` public half is in server's `~/.ssh/authorized_keys` |
| Migrations not applied | Run `docker compose -f docker-compose.production.yml exec backend python manage.py migrate` after deploy |
| `ModuleNotFoundError: No module named 'dotenv'` on container start | `requirements.txt` was missing `python-dotenv` (already fixed — if you see this again, check `requirements.txt` still has it) |
