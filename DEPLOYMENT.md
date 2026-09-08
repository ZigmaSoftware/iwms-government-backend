# IWMS Government Backend — Deployment & Testing Guide

Full flow: local setup → Docker build → server install → GitHub Actions →
how to test each stage. Backend runs on **port 9001**.

Branch policy: `sathya`/`lux`/`sameer`/`vinoth` (personal) → `dev`
(integration, tests only) → `main` (production, tests + build + deploy).

Public URL once deployed: `http://115.245.93.26:9001`

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
This is what `deploy/`, `Dockerfile`, `docker-compose.yml` etc. below refer
to as "this repo" on the server — the same files as your local clone, just
checked out here too so `docker compose` and the systemd unit have
something to run from.

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
| `.dockerignore` | Keeps venv/media/tests out of the image |
| `docker-compose.yml` | Runs the built image on the server |
| `.github/workflows/deploy.yml` | CI/CD: test → build & push image → deploy |
| `deploy/systemd/iwms-government-backend.service` | Server-only unit file (gitignored, not pushed to GitHub) |
| `deploy/cron/generate-daily-trips.cron` | Nightly trip-generation schedule, baked into the image (committed) |
| `deploy/docker-entrypoint.sh` | Starts cron + gunicorn together as the container's main process (committed) |

---

## 1a. Nightly trip scheduler — now runs INSIDE the container

The old `scheduler.sh` + host crontab setup is replaced. There is no more
host-level cron for this job — it travels with the image instead.

- **What runs:** `python manage.py generate_daily_trips`, daily at 00:05,
  same command and same Django management command as before
  ([app/management/commands/generate_daily_trips.py](app/management/commands/generate_daily_trips.py)).
- **Where it runs:** inside the backend container, via `cron` installed in
  the `Dockerfile`. `deploy/docker-entrypoint.sh` starts `cron` in the
  background, then runs gunicorn in the foreground — both share the one
  container.
- **Env vars:** cron does not inherit the container's `--env-file .env`
  variables by default, so the entrypoint dumps them to
  `/etc/container_environment.sh`, and the cron job sources that file
  before running `manage.py`. If you add new env vars to `.env`, no extra
  step is needed — they flow through automatically on the next container
  start.
- **Logs:** the cron job redirects output to the container's stdout/stderr
  (`/proc/1/fd/1`/`2`), so it shows up in `docker compose logs backend`
  alongside gunicorn's own logs, instead of the old
  `logs/generate_daily_trips.log` file on the host.
- **Manual run / testing a specific date** (same idea as before, run
  inside the container instead of a venv):
  ```bash
  docker compose exec backend python manage.py generate_daily_trips
  docker compose exec backend python manage.py generate_daily_trips --date 2026-06-26
  ```

### Migration status
`scheduler.sh` has been removed from this repo — the nightly job now lives
entirely in the container (see above). If the **server** still has an old
host crontab entry calling the old script path, remove it once the
container cron job is confirmed working (see the cron test steps below):
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

Copy this repo's `docker-compose.yml` into that same folder.

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

## 3. Test locally BEFORE touching the server

This is the important part — verify the image works on your machine first,
so if something's broken you find out in seconds, not after an SSH deploy.

### Step 1 — Build the image locally
```bash
cd /home/admin/iwms/government/webapp/iwms-government-backend
docker build -t iwms-gov-backend-test .
```
✅ Expect: build finishes with no errors, ends with `naming to
docker.io/library/iwms-gov-backend-test`.

### Step 2 — Run it locally with your real `.env`
```bash
docker run --rm -p 9001:9001 --env-file .env iwms-gov-backend-test
```
✅ Expect: gunicorn log lines like `Listening at: http://0.0.0.0:9001`.

### Step 3 — Hit it from another terminal
```bash
curl -i http://127.0.0.1:9001/
```
✅ Expect: an HTTP response (200/301/404 are all fine — anything means the
server answered). A connection error means the container isn't listening.

### Step 4 — Run the test suite the same way CI will
```bash
docker run --rm iwms-gov-backend-test python -m pytest tests/ -q
```
✅ Expect: `X passed` with no failures. Fix any failures before pushing —
this is exactly what the GitHub Actions `test` job will run.

### Step 5 — Confirm the cron job is actually installed and runs
This is new — test it explicitly, don't assume it works:
```bash
# with the container from step 2 still running, in another terminal:
docker exec -it <container_id_or_name> crontab -l
# ✅ Expect: the generate-daily-trips line to be listed

docker exec -it <container_id_or_name> ps aux | grep cron
# ✅ Expect: a running `cron` process

# force-run the job right now instead of waiting for 00:05:
docker exec -it <container_id_or_name> bash -c \
  ". /etc/container_environment.sh && cd /app && python manage.py generate_daily_trips"
# ✅ Expect: it runs without a settings/DB-connection error, proving the
# env vars reached the cron job correctly. Check `docker logs` afterwards
# too — this is where the real nightly run's output will land.
```

### Step 6 — Stop the local container
Press `Ctrl+C` in the terminal running `docker run` (step 2).

---

## 4. The git branch workflow that drives deployment

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
docker compose -f /home/admin/localserver/iwmsGovernment/iwms-government-backend/docker-compose.yml logs -f backend
curl -i http://127.0.0.1:9001/
curl -i http://115.245.93.26:9001/     # from your own machine, over the network
```
✅ Expect: the container is `Up`, logs show gunicorn serving requests, and
both curl commands return a response.

---

## 5. Manual deploy (bypassing Actions, if ever needed)

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
docker compose pull
docker compose up -d
docker compose logs -f backend
docker image prune -f
```

## 6. Rollback

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
docker compose down
docker pull ghcr.io/zigmasoftware/iwms-government-backend:<previous-commit-sha>
# edit docker-compose.yml image tag to that sha, then:
docker compose up -d
```

## 7. Quick troubleshooting

| Symptom | Check |
|---|---|
| `docker compose pull` fails | `docker login ghcr.io` again, or package visibility |
| Container exits immediately | `docker compose logs backend` — usually a missing `.env` value |
| `curl` connection refused | `sudo ufw status`, `systemctl status iwms-government-backend.service` |
| Actions `deploy` job fails at SSH step | Confirm `SERVER_SSH_KEY` public half is in server's `~/.ssh/authorized_keys` |
| Migrations not applied | Add `docker compose exec backend python manage.py migrate` after deploy, or bake it into an entrypoint script |
