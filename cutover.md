# IWMS Government — Docker cutover runbook

Migrates the live `iwms-government-{backend,frontend}` services from
venv/`runserver` + `npm run dev` to Docker containers.

**Read this first:** the current services have been up 4+ weeks and are serving
real traffic. Steps 1–3 are non-disruptive (build and test alongside). Only
step 4 causes downtime.

---

## 0. Pre-flight

    # MySQL must be running on the host (loopback only, by design)
    systemctl is-active mariadb

    # These must NOT be touched — different project
    #   iwms-backend / iwms-frontend / iwms-dashboard

Confirm current state, so you can tell whether anything changed later:

    systemctl is-active iwms-government-backend iwms-government-frontend
    curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9001/api/v1/masters/districts/
    curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/

## 1. Build both images (safe — does not touch running services)

    cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
    docker compose -f docker-compose.production.yml build

    cd /home/admin/localserver/iwmsGovernment/iwms-government-frontend
    docker compose build

The frontend build inlines `VITE_API_PROD=http://115.245.93.26:9001/api/v1`
into the bundle. Verify it actually landed:

    docker run --rm --entrypoint sh \
      ghcr.io/zigmasoftware/iwms-government-frontend:latest \
      -c 'grep -ro "115\.245\.93\.26:9001" dist/assets | head -1'

Empty output means the build args did not reach Vite — stop and fix before
cutting over.

## 2. Smoke-test the backend image on a spare port (still non-disruptive)

Port 9001 is in use by the live service, so test on 9101. Host networking
means the port comes from the CMD, so override it:

    cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
    docker run --rm --env-file .env --network host \
      ghcr.io/zigmasoftware/iwms-government-backend:latest \
      gunicorn config.wsgi:application --bind 127.0.0.1:9101 --workers 1

In another shell — this proves the container can reach MySQL on loopback,
which is the single riskiest part of the migration:

    curl -sS -o /dev/null -w 'API: %{http_code}\n' \
      http://127.0.0.1:9101/api/v1/masters/districts/

`200` = success. `500` = DB unreachable; do not proceed.
Ctrl-C the container when done.

## 3. Install the systemd units (no effect until enabled)

    cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
    sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/

    cd /home/admin/localserver/iwmsGovernment/iwms-government-frontend
    sudo cp deploy/systemd/iwms-government-frontend.service /etc/systemd/system/

    sudo systemctl daemon-reload

## 4. Cutover — DOWNTIME STARTS HERE

The new units reuse the existing unit names, so the old ones must stop first
or the port binds collide.

    # Stop the old venv/npm services
    sudo systemctl stop iwms-government-backend iwms-government-frontend

    # Confirm 9001 and 3000 are free before continuing
    sudo ss -lntp | grep -E ':(9001|3000)' || echo "both ports free"

    # Start the Docker-backed services
    sudo systemctl enable --now iwms-government-backend iwms-government-frontend

    # Watch them come up
    systemctl status iwms-government-backend --no-pager -n 20
    systemctl status iwms-government-frontend --no-pager -n 20

## 5. Django management commands

Under host networking the service name is still `backend`:

    cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
    docker compose -f docker-compose.production.yml exec backend python manage.py migrate
    docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic --noinput

`createsuperuser` is interactive — needs a real TTY (`-it`), and only if you
actually need a new admin account (existing accounts are already in MySQL):

    docker compose -f docker-compose.production.yml exec -it backend python manage.py createsuperuser

## 6. Apache reverse proxy

    sudo a2enmod proxy proxy_http headers
    cd /home/admin/localserver/iwmsGovernment/iwms-government-frontend
    sudo cp deploy/apache/iwms-government.conf /etc/apache2/sites-available/
    sudo a2ensite iwms-government.conf

`000-default.conf`: the IWMS vhost has no `ServerName`, so it is the catch-all
default on :80. Disabling the stock default is what the config comments intend
— but phpMyAdmin at `http://192.168.1.128/phpmyadmin/` is served by this same
Apache. Verify it still works after reloading; if it breaks, re-enable
`000-default` and give the IWMS vhost an explicit `ServerName` instead.

    sudo a2dissite 000-default.conf
    sudo apachectl configtest
    sudo systemctl reload apache2
    sudo systemctl enable apache2

## 7. Verify

    curl -sS -o /dev/null -w 'frontend direct: %{http_code}\n' http://127.0.0.1:3000/
    curl -sS -o /dev/null -w 'backend direct:  %{http_code}\n' http://127.0.0.1:9001/api/v1/masters/districts/
    curl -sS -o /dev/null -w 'via apache /:    %{http_code}\n' http://127.0.0.1/
    curl -sS -o /dev/null -w 'via apache /api: %{http_code}\n' http://127.0.0.1/api/v1/masters/districts/
    curl -sS -o /dev/null -w 'phpmyadmin:      %{http_code}\n' http://192.168.1.128/phpmyadmin/

Then in a browser: `http://115.245.93.26:3000/` — log in and confirm the app
loads data. Check the network tab hits `115.245.93.26:9001`.

Login working is the key check: it proves `SECRET_KEY` survived the move
(see notes below).

---

## Rollback

    sudo systemctl disable --now iwms-government-backend iwms-government-frontend
    S=/tmp/claude-1000/-home-admin-localserver-iwmsGovernment/fed9f14e-dff4-4e9b-b047-77f52a6635ed/scratchpad
    sudo cp $S/backend.service.bak /etc/systemd/system/iwms-government-backend.service
    # restore the old frontend unit from git, or recreate: npm run dev on :3000
    sudo systemctl daemon-reload
    sudo systemctl enable --now iwms-government-backend iwms-government-frontend

Config backups (`.env`, both composes) are in `$S/backup/`.
Note: the scratchpad is session-scoped — copy anything you want to keep.

---

## What was changed, and why

**backend/.env**
- `SECRET_KEY`: each `$` escaped to `$$`. Compose interpolates `env_file`
  values, and the key contains 4 `$` — including a `$(...)` sequence. Left
  alone, the container received a **56-char** key instead of the real 66-char
  one, which would have invalidated every session and password-reset token.
  Verified through the real compose path: the container now receives a key
  whose SHA-256 prefix (`683f6f5638b1`) matches the current value exactly.
  Django reads the de-escaped single-`$` value; do not "fix" the `$$`.
- `DB_ENGIBNE` → `DB_ENGINE`. Typo; settings.py reads `DB_ENGINE` and only
  worked because the fallback default happened to be mysql.

**backend/docker-compose.production.yml**
- Added `network_mode: host` and removed `ports:`. MySQL is bound to
  `127.0.0.1` only, so a bridged container cannot reach it at any address
  (3306 is refused even on 192.168.1.128). Host networking keeps
  `DB_HOST=localhost` working with no MySQL change and no new grants — the
  DB stays loopback-only.

**frontend/.env**
- `VITE_ENV=local` → `prod`, activating
  `VITE_API_PROD=http://115.245.93.26:9001/api/v1`. The old value
  (`127.0.0.1:8000`) had the wrong port and pointed at the *browser's* own
  machine. Note this also changes what local `npm run dev` talks to.

**frontend/Dockerfile + docker-compose.yml**
- `.dockerignore` excludes `.env`, so `npm run build` inside the image saw no
  `VITE_*` at all and would have produced a bundle calling `undefined/api/v1`
  — building cleanly and failing only at runtime. Values are now passed as
  build args from the host `.env`.
- Added `build:` to the compose file; it referenced a GHCR image that was
  never pushed, so `up -d` could not have worked.

**systemd units** (both `deploy/systemd/`)
- Added `network-online.target` ordering (plain `network.target` does not
  guarantee a usable network), `mariadb.service` ordering for the backend,
  orphan cleanup, and `TimeoutStartSec=0` for slow first pulls.
- The frontend unit is new — `deploy/systemd/` did not exist, so the original
  `cp` command would have failed.

## Known issues, not fixed here

1. **Secrets are in git history.** `.env` is gitignored now but was committed
   in 5 earlier commits, exposing `SECRET_KEY`, the MySQL root password and
   the Gmail app password. Rotate them; gitignoring does not remove history.
2. **DB user is `root`.** The app should have its own least-privilege MySQL
   user rather than root.
3. **Trip scheduler.** Runs in-process via `AppConfig.ready()` with a DB lock,
   so no cron entry is needed — correct as-is. But with `--workers 3` the lock
   is what prevents duplicate runs; if trips ever double up, look there first.
4. **`FIREBASE_CREDENTIALS_PATH`** points at `/Users/zigma-mac/...`, a macOS
   developer path that does not exist on this server or in the container.
   Push notifications will fail until it points at a real file (and it needs
   to be mounted into the container).
5. **HTTP only.** No TLS anywhere, and the app is reachable on a public IP.
   Consider Let's Encrypt on the Apache vhost.
