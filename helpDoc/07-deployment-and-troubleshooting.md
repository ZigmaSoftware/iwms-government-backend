# 07 — Deployment and Troubleshooting

**Production deployment is now Docker-based, driven by GitHub Actions.**
The bare-metal steps (`uv venv`/`server_uv_sync.sh`/`runserver`) still apply
for **local development**, but the server no longer runs the app directly —
it runs a container built and pushed by CI on every push to `main`. Full
step-by-step instructions, including local testing before you ever touch
the server, live in **[DEPLOYMENT.md](../DEPLOYMENT.md)** at the repo root.
This section stays focused on the *shape* of it plus troubleshooting.

> **This server was cut over on 2026-09-08 and differs from the generic steps
> below.** The images are built **locally** (`docker compose build`), not
> pulled from GHCR — nothing was ever pushed there, so `pull` fails. The
> backend compose also uses `network_mode: host` and therefore has **no
> `ports:` key**. See
> **[09-docker-cutover-2026-09-08.md](09-docker-cutover-2026-09-08.md)** for
> what is actually running, every command used, and the open items.

## First-time setup on a server (Docker-based)

```bash
# 1. Install Docker + Compose (see DEPLOYMENT.md §2 for the full version)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# 2. Create the deploy directory and drop a production .env there
sudo mkdir -p /home/admin/localserver/iwmsGovernment/iwms-government-backend
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
nano .env        # real production values — never commit this file

# 3. Place docker-compose.production.yml from the repo in that same folder, then:
# On THIS server the image is built locally — `pull` fails because nothing
# was ever pushed to GHCR. See 09-docker-cutover-2026-09-08.md.
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d

# 4. Install the systemd unit so Docker restarts the container on boot/crash
#    (now tracked in deploy/systemd/ — it exists in the repo)
sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now iwms-government-backend.service

# 5. Open the firewall port
sudo ufw allow 9001/tcp && sudo ufw reload
```

Migrations, `collectstatic`, and creating a superuser now happen **inside**
the running container, not on the host:

```bash
docker compose -f docker-compose.production.yml exec backend python manage.py migrate
docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml exec backend python manage.py createsuperuser
```

### `DJANGO_ENV` decides DEBUG

```python
ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
DEBUG = ENVIRONMENT != "production"
```

On any public server, set `DJANGO_ENV=production`. **As of 2026-09-08 this
is NOT set on this server, so `DEBUG` is `True` in production** — verified
inside the running container. See
[09](09-docker-cutover-2026-09-08.md#outstanding--read-this). With `DEBUG=True`, Django
renders a full stack trace — including settings values — to anyone who
triggers an error. It also gates seeding: `manage.py seed` refuses to run
unless `DEBUG` is `True` (see [04](04-commands-reference.md)), so a
production-configured environment cannot be seeded even by accident.

## Running it for real

`runserver` is a development server — single-threaded and explicitly not for
production. The Docker image's `CMD` already runs gunicorn for you (already
a pinned dependency, `gunicorn==23.0.0`):

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:9001 --workers 3
```

The server runs Apache (already installed — confirmed to be just the
stock default page before this was set up). Apache is reused as the
reverse proxy in front of both this container and the frontend's — see
[iwms-government-frontend/DEPLOYMENT.md](../../iwms-government-frontend/DEPLOYMENT.md)
§5 for the vhost config and setup steps. Until that's done on a given
server, the container's port (9001) is reachable directly at
`http://<host>:9001`; once Apache is set up, `/api/` and `/admin/` are
reverse-proxied there and the direct port should be closed on the
firewall.

Keep the container alive across boots/crashes with the systemd unit this
repo now ships at `deploy/systemd/iwms-government-backend.service`
(gitignored — copy it onto the server yourself, see
[DEPLOYMENT.md](../DEPLOYMENT.md)). Its `ExecStart` is `docker compose -f
docker-compose.production.yml up`, not gunicorn directly — systemd
supervises the container, Docker supervises gunicorn inside it.

## `ALLOWED_HOSTS` and CORS — the two settings that break access

Both live in `config/settings.py` as hard-coded lists, not `.env` keys —
this is the single most common cause of "the API worked yesterday and now it
doesn't". The current list is long: individual developer LAN IPs (each with
an inline comment naming whose machine it is), a `.trycloudflare.com`
wildcard, and one specific `ngrok-free.dev` hostname used for a tunnel.

**`ALLOWED_HOSTS`** — the hostnames/IPs Django will answer *as*. If you
serve the API on a new address, add it here or every request returns
`DisallowedHost`.

**`CORS_ALLOWED_ORIGIN_REGEXES`** — which browser origins may call the API.
About where the *frontend* is served from — a different thing from
`ALLOWED_HOSTS`. If a developer runs the frontend on a new LAN IP, their
browser gets a CORS error until a regex covers it. `CORS_ALLOW_CREDENTIALS`
is `True`, so cookies/auth headers are allowed cross-origin for whatever
matches.

If you add an entry to either list, add a comment saying whose machine it
is — matching the existing convention — and remove it when that machine is
gone. Both lists have already grown a long tail; don't let them grow
silently.

## The shell scripts this repo actually ships

- **`manage.sh`** — thin wrapper around `manage.py`: uses
  `.venv/bin/python manage.py "$@"` if a venv exists, else falls back to
  `uv run python manage.py "$@"`. Use this instead of remembering whether a
  venv is active. Local development only.
- **`server_uv_sync.sh`** — wraps `uv sync --locked` for local/manual
  environment setup, with a DNS reachability check and a note to fall back
  to reusing an existing venv if offline for package downloads. Not part of
  the deploy path anymore (Docker images install dependencies at build
  time instead) — this is now a local convenience script only.

### Nightly trip generation — the app schedules itself, no cron involved

`scheduler.sh` and the old host crontab entry are **gone**, and no
replacement cron job was added to the Docker image either — one was tried
and then removed once it turned out to be redundant. The app already
schedules this job **itself**, in-process:

- **Runs via**: `app/services/daily_trip_scheduler.py`, a background
  thread started automatically by `AppConfig.ready()`
  ([app/apps.py](../app/apps.py)) the moment Django starts — no cron,
  no external scheduler process, nothing to install in the image.
- **When**: `04:00` by default. A DB-backed `SchedulerConfig` singleton
  row takes priority if present (changeable live, no restart); otherwise
  the `DAILY_TRIP_SCHEDULER_TIME` env var (`HH:MM`). Set
  `ENABLE_DAILY_TRIP_JOB_SCHEDULER=false` to disable it entirely.
- **Multi-worker safety**: gunicorn runs 3 workers, so 3 copies of this
  thread start — but `run_daily_trip_job` takes a MySQL
  `GET_LOCK`/`RELEASE_LOCK` keyed by date before running, so only one
  worker's copy actually executes the job.
- **Doesn't fire for management commands**: `migrate`, `seed`,
  `generate_daily_trips` itself, etc. are excluded, so running those
  inside the container never double-triggers the scheduler.
- **Logs**: normal Python `logging` → container stdout/stderr →
  `docker compose -f docker-compose.production.yml logs backend`, same as
  everything else.
- **Manual run** (e.g. to test, or backfill a missed night — unrelated to
  the scheduler thread, just calls the command directly):
  ```bash
  docker compose -f docker-compose.production.yml exec backend python manage.py generate_daily_trips
  docker compose -f docker-compose.production.yml exec backend python manage.py generate_daily_trips --date 2026-06-26
  ```

Full detail: [DEPLOYMENT.md](../DEPLOYMENT.md) §1a.

## Verifying a deployment

```bash
sudo systemctl status iwms-government-backend.service   # container supervised & up
docker compose -f docker-compose.production.yml logs -f backend   # gunicorn output (scheduler logs interleave here too)

curl -i http://127.0.0.1:9001/                     # from the server itself
curl -i http://115.245.93.26:9001/                 # confirms the port is reachable externally
curl -i http://115.245.93.26:9001/api/v1/          # the grouped API index
```

Then open `http://115.245.93.26:9001/api/v1/swagger/` and try a real login
through it. A successful login returning both an access token and a
refresh token proves the database, settings, `SECRET_KEY` and JWT config
are all working together — see [01](01-architecture-overview.md) for why
there are two tokens here.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Table 'iwmsdbGovernment...' doesn't exist` | Pulled code, didn't migrate | `makemigrations app` then `migrate` |
| `django.db.utils.OperationalError: Access denied` | Wrong `DB_USER`/`DB_PASSWORD`, or no `.env` | Check `.env` exists and matches the MySQL user |
| `Can't connect to MySQL server` | MySQL not running, or wrong `DB_HOST`/`DB_PORT` | `sudo systemctl start mariadb`; verify host and port |
| Changing `DB_ENGINE` in `.env` does nothing | The key is misspelled `DB_ENGIBNE` in `.env` | Edit `config/settings.py`'s default directly, or fix the key name — see [02](02-database-and-env.md) |
| `DisallowedHost at /` | Address missing from `ALLOWED_HOSTS` | Add it in `config/settings.py`, with a comment naming whose machine it is |
| Browser: "blocked by CORS policy" | Frontend origin not matched | Add a regex to `CORS_ALLOWED_ORIGIN_REGEXES` |
| `401 Unauthorized` on every call | Access token expired (5h lifetime) | Use the `login/refresh-token` endpoint, or log in again |
| Refresh also fails after 7 days | Refresh token lifetime expired (not rotated/blacklisted, so it's simply gone) | Log in again |
| Everyone logged out at once | `SECRET_KEY` changed — it signs both access and refresh JWTs | Restore the key, or accept the one-time re-login |
| `ImproperlyConfigured: SECRET_KEY` | `.env` missing or `SECRET_KEY` empty | Fill it in — no `.env.example` yet, see [02](02-database-and-env.md) |
| Deleted a file, Django still imports it | Stale `__pycache__` | Clear caches — see [04](04-commands-reference.md) |
| `makemigrations` says "no changes" but the table is wrong, or two conflicting `0002_*` files appear | Migration state out of step with models — this repo has a live example already | Locally: drop and rebuild (see [02](02-database-and-env.md)) |
| Uploaded images 404 after deploy | `DEBUG=False`, so Django no longer serves `media/` | Check the `./media:/app/media` volume mount in `docker-compose.production.yml` is present and the path actually has the files |
| OTP / reset mail never arrives | `EMAIL_*` wrong, or SMTP blocks the login | Verify `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`; Gmail needs an app password |
| Push notifications silently never send | `FIREBASE_CREDENTIALS_PATH` unset, or `firebase-admin` not installed | Confirm the path in `.env`, and check `firebase-admin` actually installed (`pyproject.toml` is missing it even though `requirements.txt` has it — see [04](04-commands-reference.md)) |
| Route optimisation fails | `ORS_API_KEY` missing or over quota | Check the key in `.env` |
| No trips generated overnight | The in-process scheduler thread didn't fire — e.g. `ENABLE_DAILY_TRIP_JOB_SCHEDULER=false`, the container restarted right at the scheduled time, or all 3 gunicorn workers' threads lost the DB lock race unexpectedly | `docker compose -f docker-compose.production.yml logs backend` around the scheduled time for a traceback; run `docker compose -f docker-compose.production.yml exec backend python manage.py generate_daily_trips --date <missed-date>` to backfill (idempotent, safe to re-run) |
| A staff member sees zero rows on a list screen they should have access to | No `StaffDataScope` row resolves for them — default-deny, not a bug | Grant them a `StaffDataScope` for the right geography level |
| Tests fail on MySQL specifics | Tests use SQLite in-memory | Expected — see [08](08-unit-testing-guide.md) |

## Reading logs

```bash
journalctl -u iwms-government-backend.service -f   # systemd's view of the container lifecycle
docker compose -f docker-compose.production.yml logs -f backend   # gunicorn AND the in-process scheduler, combined
docker compose -f docker-compose.production.yml logs --since 24h backend | grep generate_daily_trips
```

With `DEBUG=False` Django writes tracebacks to stderr, which Docker
captures as container logs. If Apache is set up in front as a reverse
proxy (see above), its own logs are separate:
`/var/log/apache2/iwms-government-error.log` and `-access.log`.

Next: [08-unit-testing-guide.md](08-unit-testing-guide.md).
