# 09 — Docker cutover (2026-09-08)

What actually happened when this server moved from bare-metal
(`.venv` + `runserver`) to Docker, what had to be fixed to make it work, and
what is still outstanding. Written from the real cutover, so the surprises are
included — [07](07-deployment-and-troubleshooting.md) describes the intended
shape, this file describes the machine as it is now.

## Before and after

| | Before | After |
|---|---|---|
| Backend | `.venv/bin/python manage.py runserver 0.0.0.0:9001` | container, `gunicorn --workers 3` |
| Frontend | `npm run dev` (Vite dev server) | container, `serve -s dist` |
| Restarts | systemd ran the venv/npm process | systemd runs `docker compose up` |
| Port 9001 | bound by Django directly | bound by gunicorn via `network_mode: host` |

Both services had been up **4+ weeks** on the old setup. The unit names were
reused, so the old units had to stop before the new ones could bind.

## The database decision: `network_mode: host`

This is the most important thing in this file.

MySQL/MariaDB runs on the **host**, not in the compose stack, and is bound to
loopback only:

```
bind-address = 127.0.0.1
```

A container on the default bridge network therefore **cannot reach it at any
address** — `192.168.1.128:3306` refuses connections just as `localhost` does
from inside a bridged container. Confirmed during cutover.

Two ways out; we took the first:

1. **`network_mode: host`** — the container shares the host's network stack,
   so `DB_HOST=localhost` keeps working with no MySQL change, no new grants,
   and the DB stays loopback-only.
2. Open MySQL to the docker bridge (`bind-address` += `172.17.0.1`, a
   `root@'172.17.%'` grant, `DB_HOST=host.docker.internal`). More moving
   parts, and it exposes MySQL beyond loopback.

Verified from inside the running container:

```
DB CONNECTED: iwmsdbGovernment on MariaDB 11.8.6, 142 tables
```

### Consequence: no `ports:` key

`docker-compose.production.yml` has **no `ports:` mapping**, and that is not an
omission — compose rejects `ports:` together with `network_mode: host`:

```
"ports" cannot be used with "network_mode: host"
```

The port comes from the Dockerfile `CMD` (`gunicorn --bind 0.0.0.0:9001`).
`docker ps` shows an **empty PORTS column** for this container while
`ss -lntp` shows `0.0.0.0:9001` — expected, not a fault.

To change the port, edit the gunicorn `--bind` in the Dockerfile, or override
`command:` in the compose file. Host mode also ignores `EXPOSE` and publishes
on **all** interfaces, so 9001 is open on the public IP.

## `SECRET_KEY` — do not "fix" the `$$`

The key in `.env` contains **4 `$` characters**, one of them a `$(...)`
sequence. Compose interpolates `env_file` values, so the unescaped key was
silently truncated **66 chars → 56** on its way into the container. A
different `SECRET_KEY` invalidates every session cookie and every
password-reset token.

Each `$` is therefore escaped as `$$` in `.env`. Compose collapses `$$` → `$`
at container start, so Django receives the original 66-char value. Verified by
comparing SHA-256 through the real compose path.

> **If you see `$$` in `SECRET_KEY`, leave it.** Changing it to a single `$`
> logs out every user.

Two related traps:

- `docker compose config` prints the value **before** the `$$` → `$` collapse,
  so it looks wrong there. It isn't.
- `docker run --env-file` does **not** interpolate at all, so a container
  started that way gets the literal `$$` — a different key. Fine for a DB
  connectivity check; useless for testing login.

## Other fixes the cutover required

**`DB_ENGIBNE` → `DB_ENGINE`** in `.env`. Typo; `settings.py` reads
`DB_ENGINE` and only worked because the fallback default was already mysql.

**systemd unit** (`deploy/systemd/iwms-government-backend.service`) now orders
after `network-online.target` (plain `network.target` does not guarantee a
usable network) and `mariadb.service`, tears down orphans on start, and sets
`TimeoutStartSec=0` for slow first pulls. `ExecStart` uses `up` **without**
`-d` on purpose: compose stays in the foreground so systemd tracks it as the
main process and `Restart=always` works.

## Verifying this server

```bash
docker ps --filter name=iwms-government
curl -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9001/api/v1/masters/districts/   # 401 = healthy
```

`401` is the correct healthy answer on that endpoint — auth rejecting an
unauthenticated request proves the request reached Django and Django reached
MySQL. A DB failure shows as `500`.

Logs, from the repo directory:

```bash
docker compose -f docker-compose.production.yml logs -f
docker compose -f docker-compose.production.yml logs --tail 50
```

Management commands run **inside** the container:

```bash
docker compose -f docker-compose.production.yml exec backend python manage.py migrate
docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml exec -it backend python manage.py createsuperuser   # -it required
```

`createsuperuser` is interactive and hangs without `-it`. It is also rarely
needed — existing admin accounts live in MySQL and survive the cutover.

## Outstanding — read this

1. **`DEBUG = True` in production.** `DJANGO_ENV` is **not set** in `.env`, and
   `DEBUG = ENVIRONMENT != "production"`, so DEBUG is on right now on a
   public-facing server. Any unhandled error renders a stack trace with
   settings values to whoever triggered it. Fix:

   ```bash
   echo 'DJANGO_ENV=production' >> .env
   sudo systemctl restart iwms-government-backend
   ```

   Note this also disables `manage.py seed` by design, and turns off Django's
   static-file serving — `collectstatic` plus a real static route must work
   first. Do it deliberately, not blind.

2. **Secrets are in git history.** `.env` is gitignored *now*, but was
   committed in 5 earlier commits, exposing `SECRET_KEY`, the MySQL root
   password, and the Gmail app password. Gitignoring does not remove history —
   rotate all three. See [06](06-gitignore-and-secrets.md).

3. **DB user is `root`.** The app should have a least-privilege MySQL user
   scoped to `iwmsdbGovernment`.

4. **`FIREBASE_CREDENTIALS_PATH`** points at `/Users/zigma-mac/Documents/...`,
   a macOS developer path that exists neither on this server nor in the
   container. Push notifications fail until it points at a real file **and**
   that file is mounted into the container (add it to `volumes:`).

5. **HTTP only, public IP.** No TLS anywhere. Consider Let's Encrypt on the
   Apache vhost.

6. **Trip scheduler + `--workers 3`.** The nightly job self-schedules
   in-process from `AppConfig.ready()` (no cron — see
   [07](07-deployment-and-troubleshooting.md)), and a DB lock is what stops
   all 3 gunicorn workers running it. If trips ever duplicate, look there
   first.

---

# Command reference — every command, in order

Copy-paste ready. Run from the repo root unless a `cd` is shown.
`BE=/home/admin/localserver/iwmsGovernment/iwms-government-backend`

## A. Permissions (the prerequisite nobody expects)

The repo is owned `admin:iwmsuser` with group-write and setgid, but `admin`
was not in the `iwmsuser` group, so `mkdir deploy/systemd` failed with
`EACCES`:

```bash
sudo usermod -aG iwmsuser admin
newgrp iwmsuser            # or log out/in — group lists are fixed at login
id                         # must now list 1007(iwmsuser)
```

In VS Code, a new terminal tab is **not** enough — reload the remote window
(the VS Code server process still holds the old group list).

Vite's cache also needed group write (see the frontend doc — this is what took
the old dev server down):

```bash
chmod -R g+w /home/admin/localserver/iwmsGovernment/iwms-government-frontend/node_modules/.vite
```

## B. Pre-flight — record the state you are leaving

```bash
systemctl is-active iwms-government-backend iwms-government-frontend
sudo ss -lntp | grep -E ':(9001|3000)'
curl -o /dev/null -w 'backend: %{http_code}\n' http://127.0.0.1:9001/api/v1/masters/districts/
docker ps -a
systemctl is-active mariadb
```

Leave `iwms-backend`, `iwms-frontend`, `iwms-dashboard` alone — different
project on the same box.

## C. Build (non-disruptive — the running services keep serving)

```bash
cd $BE
docker compose -f docker-compose.production.yml build
docker images | grep iwms-government-backend      # must print a row
```

The build takes a few minutes (compiles `mysqlclient` and Pillow) and ends
with `naming to ghcr.io/zigmasoftware/iwms-government-backend:latest`.

> `docker run` on an image you have not built fails with
> `ghcr.io/...: not found` — the GHCR image was never pushed, so **build is
> not optional**.

## D. Prove the container reaches MySQL (still non-disruptive)

Port 9001 is busy, so test on 9101:

```bash
cd $BE
docker run --rm --env-file .env --network host \
  ghcr.io/zigmasoftware/iwms-government-backend:latest \
  gunicorn config.wsgi:application --bind 127.0.0.1:9101 --workers 1
```

In a second terminal:

```bash
curl -o /dev/null -w 'API: %{http_code}\n' http://127.0.0.1:9101/api/v1/masters/districts/
```

`401` = healthy. `500` = DB unreachable, **stop**. Then `Ctrl+C`.

Explicit DB check (clearer than inferring from the status code):

```bash
docker run --rm --env-file .env --network host \
  ghcr.io/zigmasoftware/iwms-government-backend:latest \
  python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute('SELECT DATABASE(), VERSION()')
    print('DB CONNECTED:', *c.fetchone())
"
```

## E. Install the systemd unit

```bash
cd $BE
sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
```

Inspect before or after:

```bash
cat $BE/deploy/systemd/iwms-government-backend.service      # repo version (new)
cat /etc/systemd/system/iwms-government-backend.service     # installed version
systemctl cat iwms-government-backend                       # what systemd has loaded
diff /etc/systemd/system/iwms-government-backend.service \
     $BE/deploy/systemd/iwms-government-backend.service     # what the cutover changes
systemd-analyze verify $BE/deploy/systemd/iwms-government-backend.service
```

## F. Cutover — downtime starts here

```bash
sudo systemctl stop iwms-government-backend iwms-government-frontend
sudo ss -lntp | grep -E ':(9001|3000)' || echo "both ports free"
sudo systemctl enable --now iwms-government-backend iwms-government-frontend
systemctl status iwms-government-backend --no-pager -n 15
```

## G. Post-cutover Django commands

```bash
cd $BE
docker compose -f docker-compose.production.yml exec backend python manage.py showmigrations --plan | grep -c '^\[ \]'
docker compose -f docker-compose.production.yml exec backend python manage.py migrate
docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml exec -it backend python manage.py createsuperuser
```

On this server `showmigrations` reported **0** unapplied, so `migrate` was a
no-op. `createsuperuser` needs `-it` and is rarely necessary.

## H. Viewing the containers

```bash
docker ps --filter name=iwms-government
docker compose -f docker-compose.production.yml logs -f          # from $BE
docker compose -f docker-compose.production.yml logs --tail 50
docker logs -f iwms-government-backend-backend-1                 # from anywhere
docker compose -f docker-compose.production.yml exec backend bash
docker stats iwms-government-backend-backend-1
docker compose ls -a
docker inspect iwms-government-backend-backend-1
```

Portainer UI: `https://192.168.1.128:9443`.

## I. Apache reverse proxy

```bash
sudo a2enmod proxy proxy_http headers
cd /home/admin/localserver/iwmsGovernment/iwms-government-frontend
sudo cp deploy/apache/iwms-government.conf /etc/apache2/sites-available/
sudo a2ensite iwms-government.conf
sudo apachectl configtest
sudo systemctl reload apache2
```

**Check phpMyAdmin before disabling the default site** — the same Apache
serves it, and the IWMS vhost has no `ServerName`, making it the catch-all:

```bash
curl -o /dev/null -w 'phpmyadmin: %{http_code}\n' http://192.168.1.128/phpmyadmin/
sudo a2dissite 000-default.conf
sudo apachectl configtest && sudo systemctl reload apache2
curl -o /dev/null -w 'phpmyadmin after: %{http_code}\n' http://192.168.1.128/phpmyadmin/
sudo systemctl enable apache2
```

If phpMyAdmin breaks, undo it:

```bash
sudo a2ensite 000-default.conf && sudo systemctl reload apache2
```

## J. Verify

```bash
curl -o /dev/null -w 'frontend :3000 -> %{http_code}\n' http://127.0.0.1:3000/
curl -o /dev/null -w 'backend  :9001 -> %{http_code}\n' http://127.0.0.1:9001/api/v1/masters/districts/
curl -o /dev/null -w 'apache /       -> %{http_code}\n' http://127.0.0.1/
curl -o /dev/null -w 'apache /api/   -> %{http_code}\n' http://127.0.0.1/api/v1/masters/districts/
```

Then in a browser: `http://115.245.93.26:3000/` — **log in**. A successful
login is the only real proof the `SECRET_KEY` escaping held.

## K. Day-to-day

```bash
# restart after an .env change
sudo systemctl restart iwms-government-backend

# rebuild after a code change, then restart
cd $BE && docker compose -f docker-compose.production.yml build
sudo systemctl restart iwms-government-backend

# check DEBUG / env inside the running container
docker compose -f docker-compose.production.yml exec -T backend python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.conf import settings
print('DJANGO_ENV:', os.getenv('DJANGO_ENV','(not set)'), '| DEBUG:', settings.DEBUG)
"
```

## L. Rollback

```bash
sudo systemctl disable --now iwms-government-backend iwms-government-frontend
# restore the previous unit (venv + runserver) from git or backup, then:
sudo systemctl daemon-reload
sudo systemctl enable --now iwms-government-backend
```

The old backend unit ran:

```
ExecStart=/home/admin/localserver/iwmsGovernment/iwms-government-backend/.venv/bin/python manage.py runserver 0.0.0.0:9001
```

## Commands NOT to run on this server

From the generic fresh-server guide — destructive or wrong here:

| Command | Why not |
|---|---|
| `git clone ...` | Already cloned. Re-cloning destroys `.env` and `media/` uploads |
| `curl -fsSL https://get.docker.com \| sh` | Docker already installed |
| `ssh-keygen -t ed25519 -f ~/.ssh/gov_deploy_key` | Deploy key already set up |
| `docker login ghcr.io` | Images are built locally; no pull needed |
| `docker compose ... pull` | Fails — the GHCR image was never pushed. Use `build` |
| `sudo ufw delete allow 9001/tcp` | The frontend calls `115.245.93.26:9001` **directly**; deleting this breaks the app |
| `DB_HOST=host.docker.internal` | Wrong with `network_mode: host`. Keep `localhost` |
| Changing `$$` → `$` in `SECRET_KEY` | Logs out every user |

---

# Docker basics for these two services

**Read this first: there are TWO supervisors.** systemd runs `docker compose
up` in the foreground, and the containers also carry `restart: always`. So a
plain `docker stop` or `docker kill` does **not** keep the container down —
compose/systemd bring it straight back.

Measured on this server:

```
docker stop iwms-government-frontend-frontend-1
t+1s  status=exited    http=000
t+2s  status=gone      http=000     <- compose removed it
t+7s  status=running   http=000     <- systemd restarted it
t+8s  status=running   http=200     <- back up, ~8s total
```

That auto-recovery is the point of the setup. But it means:

> **To actually stop a service, use `systemctl`, not `docker`.**
> Use `docker stop`/`kill` only to force a restart-in-place.

## The names you need

| | Backend | Frontend |
|---|---|---|
| systemd unit | `iwms-government-backend` | `iwms-government-frontend` |
| container | `iwms-government-backend-backend-1` | `iwms-government-frontend-frontend-1` |
| compose service | `backend` | `frontend` |
| compose file | `docker-compose.production.yml` (needs `-f`) | `docker-compose.yml` (default) |
| port | 9001 (via `network_mode: host`) | 3000 (via `ports:`) |

Shell shortcuts used below:

```bash
BE=/home/admin/localserver/iwmsGovernment/iwms-government-backend
FE=/home/admin/localserver/iwmsGovernment/iwms-government-frontend
```

## Start / stop / restart — the correct way

```bash
# STOP (stays stopped)
sudo systemctl stop iwms-government-backend
sudo systemctl stop iwms-government-frontend

# START
sudo systemctl start iwms-government-backend
sudo systemctl start iwms-government-frontend

# RESTART — the everyday command, e.g. after an .env change
sudo systemctl restart iwms-government-backend
sudo systemctl restart iwms-government-frontend

# BOTH AT ONCE
sudo systemctl restart iwms-government-backend iwms-government-frontend

# STOP AND KEEP IT OFF ACROSS REBOOTS
sudo systemctl disable --now iwms-government-backend

# TURN IT BACK ON
sudo systemctl enable --now iwms-government-backend

# IS IT RUNNING / WHY DID IT FAIL
systemctl status iwms-government-backend --no-pager -n 30
systemctl is-active iwms-government-backend iwms-government-frontend
journalctl -u iwms-government-backend -n 50 --no-pager
journalctl -u iwms-government-backend -f            # follow live
```

## Kill / force-restart a container

Legitimate when a container is wedged and you want it recreated immediately.
Both come back automatically:

```bash
# graceful stop (SIGTERM, 10s grace) — supervisor recreates it in ~8s
docker stop iwms-government-backend-backend-1

# immediate SIGKILL, no grace — use when the process ignores SIGTERM
docker kill iwms-government-frontend-frontend-1

# restart in place, keeping the same container
docker restart iwms-government-backend-backend-1
```

To stop a container **and have it stay stopped**, stop the unit first:

```bash
sudo systemctl stop iwms-government-backend
docker ps -a --filter name=iwms-government-backend
```

### If repeated `docker stop`s leave the unit `failed`

systemd rate-limits restarts (`StartLimitBurst`, default 5 starts in 10s).
Stop a container several times in quick succession and it gives up, leaving
the unit `failed` and the service genuinely down:

```bash
sudo systemctl reset-failed iwms-government-frontend
sudo systemctl start iwms-government-frontend
```

### The recreated container is a NEW container

The name is reused (`iwms-government-frontend-frontend-1`), but it is a fresh
container from the image — anything written inside it that is not on a mounted
volume is gone. The backend bind-mounts `./media` and `./static`, so uploads
and collected static files survive; the frontend mounts nothing, as it serves
only baked-in files.

## Create / recreate containers

```bash
# recreate from the current image + compose file (compose does down+up itself)
cd $BE && docker compose -f docker-compose.production.yml up -d --force-recreate
cd $FE && docker compose up -d --force-recreate

# rebuild the image, then recreate — after a CODE change
cd $BE && docker compose -f docker-compose.production.yml up -d --build
cd $FE && docker compose up -d --build

# remove containers (images and bind-mounted media/ are untouched)
cd $BE && docker compose -f docker-compose.production.yml down
cd $FE && docker compose down

# the clean way once systemd owns them:
sudo systemctl restart iwms-government-backend
```

> Prefer `systemctl restart` over `compose up -d` for routine restarts. A
> manual `up -d` detaches from systemd's foreground process, so the unit and
> reality can drift. If you do run it by hand, follow with
> `sudo systemctl restart <unit>` to hand control back.

## Inspect what is running

```bash
docker ps --filter name=iwms-government                 # just these two
docker ps -a                                            # include stopped
docker compose ls -a                                    # compose projects
docker stats iwms-government-backend-backend-1 iwms-government-frontend-frontend-1
docker inspect iwms-government-backend-backend-1
docker inspect -f '{{.State.Status}} since {{.State.StartedAt}}' iwms-government-backend-backend-1
docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' iwms-government-backend-backend-1
docker top iwms-government-backend-backend-1            # processes inside
docker port iwms-government-frontend-frontend-1         # backend shows nothing: host networking
```

## Logs

```bash
# by compose (from the repo dir)
cd $BE && docker compose -f docker-compose.production.yml logs -f
cd $BE && docker compose -f docker-compose.production.yml logs --tail 100
cd $FE && docker compose logs -f

# by container name, from anywhere
docker logs -f iwms-government-backend-backend-1
docker logs --tail 100 iwms-government-frontend-frontend-1
docker logs --since 10m iwms-government-backend-backend-1
docker logs --timestamps iwms-government-backend-backend-1

# systemd's view (includes compose's own start/stop lines)
journalctl -u iwms-government-backend -f
```

`Ctrl+C` leaves a `-f` follow; it does not affect the container.

## Get a shell inside

```bash
# backend (Debian-based, has bash)
cd $BE && docker compose -f docker-compose.production.yml exec backend bash
docker exec -it iwms-government-backend-backend-1 bash

# frontend (node:20-slim — use sh)
cd $FE && docker compose exec frontend sh
docker exec -it iwms-government-frontend-frontend-1 sh

# one-off command, no interactive shell
docker exec iwms-government-backend-backend-1 python manage.py showmigrations
docker exec iwms-government-frontend-frontend-1 ls -la dist
```

`-it` is required for anything interactive (a shell, `createsuperuser`).
Scripted/non-TTY calls need `exec -T` under compose.

## Django commands (backend only)

```bash
cd $BE
docker compose -f docker-compose.production.yml exec backend python manage.py migrate
docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml exec backend python manage.py showmigrations
docker compose -f docker-compose.production.yml exec -it backend python manage.py createsuperuser
docker compose -f docker-compose.production.yml exec -it backend python manage.py shell
```

## Images

```bash
docker images | grep iwms-government
cd $BE && docker compose -f docker-compose.production.yml build
cd $FE && docker compose build
cd $BE && docker compose -f docker-compose.production.yml build --no-cache   # ignore cache
docker image rm ghcr.io/zigmasoftware/iwms-government-backend:latest         # stop the unit first
docker history ghcr.io/zigmasoftware/iwms-government-backend:latest
```

Do **not** `docker compose pull` — these images are built locally and were
never pushed to GHCR, so a pull fails with `not found`.

## Health checks

```bash
curl -o /dev/null -w 'frontend :3000 -> %{http_code}\n' http://127.0.0.1:3000/
curl -o /dev/null -w 'backend  :9001 -> %{http_code}\n' http://127.0.0.1:9001/api/v1/masters/districts/
sudo ss -lntp | grep -E ':(3000|9001)'
```

Expected: frontend **200**, backend **401**. `401` is healthy — auth rejecting
an unauthenticated request proves Django ran and reached MySQL. `500` points
at the database; `000` means nothing is listening.

## Disk cleanup

```bash
docker system df                  # what is using space
docker image prune                # dangling images only — safe
docker container prune            # stopped containers
docker builder prune              # build cache, often the biggest win
```

Avoid `docker system prune -a` on this box: it removes images not currently
running, including `portainer` and the old `compreface` containers, and forces
a full rebuild.

## Common mistakes

| Mistake | What happens | Do instead |
|---|---|---|
| `docker stop <container>` to take a service down | comes back in ~8s | `sudo systemctl stop <unit>` |
| Editing frontend `.env` then restarting | no change — `VITE_*` is baked in at build | `docker compose build` then restart |
| `docker compose pull` | `not found` — never pushed to GHCR | `docker compose build` |
| Omitting `-f docker-compose.production.yml` on the backend | compose can't find a config | always pass `-f` for the backend |
| `docker compose` from the wrong directory | no compose file found | `cd $BE` or `cd $FE` first |
| `exec` without `-it` for `createsuperuser` | hangs waiting on a TTY | add `-it` |
| Adding `ports:` to the backend compose | compose errors — illegal with `network_mode: host` | leave it out; the port is in the Dockerfile CMD |
| `docker system prune -a` | wipes unrelated images (portainer, compreface) | `docker image prune` |

---

# GitHub Actions — how CI/CD interacts with all of this

Both repos have `.github/workflows/deploy.yml`. They are **live**: a push to
`main` deploys to this server automatically.

| Push to | What happens |
|---|---|
| `main` | build image → push to GHCR → SSH to this server → `compose pull` + `up -d` |
| `dev` | nothing — the workflow does not start (triggers are `main` only) |
| any other branch | nothing |

The deploy job SSHes in using `secrets.SERVER_HOST`, `SERVER_USER`,
`SERVER_SSH_KEY` and runs, in the repo directory:

```bash
docker compose [-f docker-compose.production.yml] pull <service>
docker compose [-f docker-compose.production.yml] up -d <service>
docker image prune -f
```

## Two supervisors, now three ways in

CI's `docker compose up -d` **detaches from systemd**. The unit's foreground
`docker compose up` process is not the one CI creates, so after a CI deploy
`systemctl status` can look healthy while the running container came from CI.
It works, but the two views drift.

After any CI deploy, hand control back to systemd:

```bash
sudo systemctl restart iwms-government-backend    # or -frontend
```

## The frontend's build-arg problem (fixed 2026-09-08)

CI ran a plain `docker build .`. Once the Dockerfile started taking `VITE_*`
build args — and with `.dockerignore` excluding `.env` from the build context —
that produced a bundle whose API base was the literal `undefined`. **A green
build, a pushed image, an app broken in the browser.**

The workflow now passes them explicitly and refuses to push a bad image:

1. **Verify build args are configured** — fails if `vars.VITE_API_PROD` is empty.
2. **Build image** — passes every `VITE_*` as `--build-arg`.
3. **Verify the API URL landed in the bundle** — greps `dist/assets` for the
   host from `VITE_API_PROD` and fails the job if absent.

### No GitHub configuration required

The values are hardcoded in the workflow. That is deliberate: **nothing in a
frontend bundle is secret.** Every `VITE_*` value is inlined into JS that any
user can download and read, the URLs are public endpoints, and the weighbridge
key is already hardcoded in `src/utils/wasteApi.ts` — a GitHub secret would add
indirection without adding protection.

A repo variable still wins if one is set:

```yaml
VITE_API_PROD: ${{ vars.VITE_API_PROD || 'http://115.245.93.26:9001/api/v1' }}
```

So a value can be overridden from the GitHub UI (Settings → Secrets and
variables → Actions → Variables) without editing the workflow — useful when the
server IP changes. Nothing breaks if no variable exists.

> If a genuinely secret value is ever needed by the frontend, it cannot go in
> the bundle at all. Proxy the call through the backend, which reads its own
> `.env` at runtime on the server.

### Why grepping for "undefined" does not work

The obvious guard — fail if the bundle contains `undefined/api` — was tried
and **verified not to work**: Vite emits a bare `undefined` literal, and
minified JS is full of unrelated `undefined`s. The working guard asserts the
real host **is** present. Confirmed against both a good and a deliberately
broken image.

## `pull` vs `build` on this server

The compose files carry **both** `image:` and `build:`:

- **CI** pushes to GHCR, then the server **pulls** — the normal path.
- **Manually** on the server, `docker compose build` builds locally, which is
  how the cutover was done because nothing had been pushed to GHCR yet.

`docker compose pull` fails with `not found` until CI has pushed at least once.
The server is already `docker login`-ed to `ghcr.io`, so pulls work once an
image exists.

## Before the next push to `main`

The cutover changed files that CI depends on. Nothing is committed yet, so CI
has not seen any of it:

| File | Why it must be committed |
|---|---|
| `docker-compose.production.yml` | `network_mode: host` — without it the container cannot reach MySQL |
| `Dockerfile` (frontend) | the `ARG`/`ENV` block CI now feeds |
| `docker-compose.yml` (frontend) | `build:` + args block |
| `.github/workflows/deploy.yml` (frontend) | the build args and guards |
| `deploy/systemd/*.service` | referenced by the runbook |

`.env` files are gitignored and stay that way — production values live on the
server and, for CI, in repo variables.

> Untested from the server: the **GHCR push** and the **SSH deploy** steps
> have never run successfully (the lowercase bug killed every run before
> them), so their permissions and secrets — `SERVER_HOST`, `SERVER_USER`,
> `SERVER_SSH_KEY`, and the org's "allow Actions to publish packages" setting
> — are unverified. If the first green build fails, it will be at one of
> those two steps.
