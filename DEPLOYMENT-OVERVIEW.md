# IWMS Government — Full Deployment Flow (Both Repos)

This is the single end-to-end runbook covering **this repo**
(`iwms-government-backend`) and its sibling `iwms-government-frontend`
together, in the order to actually run them. Each repo also has its own
detailed `DEPLOYMENT.md` with full command explanations, expected output,
and troubleshooting — this file is the quick combined checklist; go to the
per-repo doc for depth on any step.

- Backend detail: [`DEPLOYMENT.md`](DEPLOYMENT.md) (this repo)
- Frontend detail: `../iwms-government-frontend/DEPLOYMENT.md` (sibling repo)

Server: `115.245.93.26`. Backend container on port 9001, frontend
container on port 3000 — both internal only once nginx (Phase 6) is set
up; public traffic goes through nginx on port 80/443 instead.

---

## Phase 0 — What's already built (nothing to do, just context)

| Piece | Backend repo | Frontend repo |
|---|---|---|
| Container | `Dockerfile` → gunicorn `:9001` | `Dockerfile` → `serve` `:3000` |
| Deploy compose | `docker-compose.production.yml` | `docker-compose.yml` |
| CI/CD | `.github/workflows/deploy.yml` | `.github/workflows/deploy.yml` |
| systemd | `deploy/systemd/iwms-government-backend.service` | `deploy/systemd/iwms-government-frontend.service` |
| nginx config | — | `deploy/nginx/iwms-government.conf` |
| Nightly job | In-process scheduler thread, no cron | — |

---

## Phase 1 — SERVER: get the code + generate the deploy key

```bash
sudo mkdir -p /home/admin/localserver/iwmsGovernment
sudo chown -R admin:admin /home/admin/localserver/iwmsGovernment
cd /home/admin/localserver/iwmsGovernment

git clone https://github.com/ZigmaSoftware/iwms-government-backend.git
git clone https://github.com/ZigmaSoftware/iwms-government-frontend.git

ssh-keygen -t ed25519 -f ~/.ssh/gov_deploy_key -C "github-actions-deploy" -N ""
cat ~/.ssh/gov_deploy_key.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys && chmod 700 ~/.ssh
cat ~/.ssh/gov_deploy_key       # copy this — needed in Phase 3
```

## Phase 2 — SERVER: install Docker, create `.env`, log in to GHCR

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
nano .env        # real production DB creds, SECRET_KEY, etc.

echo <YOUR_GITHUB_PAT> | docker login ghcr.io -u <github-username> --password-stdin
```

## Phase 3 — GITHUB: add secrets (both repos)

Repo → Settings → Secrets and variables → Actions → New repository
secret, on **both** `iwms-government-backend` and
`iwms-government-frontend`:
- `SERVER_HOST` = `115.245.93.26`
- `SERVER_USER` = `admin`
- `SERVER_SSH_KEY` = the private key text from Phase 1

## Phase 4 — SERVER: install systemd units for both containers

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/

cd /home/admin/localserver/iwmsGovernment/iwms-government-frontend
sudo cp deploy/systemd/iwms-government-frontend.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable iwms-government-backend.service iwms-government-frontend.service
```

## Phase 5 — SERVER: retire the old cron-based deploy scripts

```bash
crontab -l           # remove any lines calling scheduler.sh / frontend_sync.sh / backend_sync.sh
crontab -e
```

## Phase 6 — SERVER: nginx takes over from Apache

```bash
# Apache confirmed to be just the stock default page — safe to disable
sudo systemctl disable --now apache2

sudo apt update && sudo apt install -y nginx

cd /home/admin/localserver/iwmsGovernment/iwms-government-frontend
sudo cp deploy/nginx/iwms-government.conf /etc/nginx/sites-available/iwms-government.conf
sudo ln -s /etc/nginx/sites-available/iwms-government.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t && sudo systemctl reload nginx
sudo systemctl enable nginx

sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

## Phase 7 — GITHUB: push through the branch chain (per repo)

```
sathya → PR → dev     (triggers: "test" job only)
dev → PR → main       (triggers: test → build-and-push → deploy)
```

```bash
git checkout dev && git merge sathya && git push origin dev
# check Actions tab: only "test" runs

git checkout main && git merge dev && git push origin main
# check Actions tab: test → build-and-push → deploy, all green
```

## Phase 8 — Verify everything end-to-end

```bash
sudo systemctl status nginx iwms-government-backend.service iwms-government-frontend.service

curl -i http://115.245.93.26/              # frontend, via nginx
curl -i http://115.245.93.26/api/v1/       # backend, via nginx
```

---

## Note on scope

This file references the sibling `iwms-government-frontend` repo (paths,
its systemd unit, its nginx config) even though it lives in this
(`iwms-government-backend`) repo — it's meant as the one combined
checklist for standing up both services together. The frontend repo does
not have a copy of this file; its own `DEPLOYMENT.md` stays scoped to
itself.
