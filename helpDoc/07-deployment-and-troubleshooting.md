# 07 — Deployment and Troubleshooting

**Production deployment is now Docker-based, driven by GitHub Actions.**
The bare-metal steps (`uv venv`/`server_uv_sync.sh`/`runserver`) still apply
for **local development**, but the server no longer runs the app directly —
it runs a container built and pushed by CI on every push to `main`. Full
step-by-step instructions, including local testing before you ever touch
the server, live in **[DEPLOYMENT.md](../DEPLOYMENT.md)** at the repo root.
This section stays focused on the *shape* of it plus troubleshooting.

## First-time setup on a server (Docker-based)

```bash
# 1. Install Docker + Compose (see DEPLOYMENT.md §2 for the full version)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# 2. Create the deploy directory and drop a production .env there
sudo mkdir -p /home/admin/localserver/iwmsGovernment/iwms-government-backend
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
nano .env        # real production values — never commit this file

# 3. Place docker-compose.yml from the repo in that same folder, then:
docker login ghcr.io -u <github-username>     # so `docker compose pull` can fetch the image
docker compose pull
docker compose up -d

# 4. Install the systemd unit so Docker restarts the container on boot/crash
#    (kept locally in deploy/systemd/, gitignored — copy it yourself)
sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now iwms-government-backend.service

# 5. Open the firewall port
sudo ufw allow 9001/tcp && sudo ufw reload
```

Migrations, `collectstatic`, and creating a superuser now happen **inside**
the running container, not on the host:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py collectstatic --noinput
docker compose exec backend python manage.py createsuperuser
```

### `DJANGO_ENV` decides DEBUG

```python
ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
DEBUG = ENVIRONMENT != "production"
```

On any public server, set `DJANGO_ENV=production`. With `DEBUG=True`, Django
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

There is **no nginx or reverse proxy in front of this** — confirmed the
server runs Apache, not nginx, and nginx isn't installed anywhere on this
machine. The container's port (9001) is opened directly on the firewall
and reached at `http://115.245.93.26:9001`. If you ever want TLS or a
proper domain in front of it, that would mean configuring Apache (already
on the host) as a reverse proxy — a separate task, not something this repo
sets up.

Keep the container alive across boots/crashes with the systemd unit this
repo now ships at `deploy/systemd/iwms-government-backend.service`
(gitignored — copy it onto the server yourself, see
[DEPLOYMENT.md](../DEPLOYMENT.md)). Its `ExecStart` is `docker compose up`,
not gunicorn directly — systemd supervises the container, Docker supervises
gunicorn inside it.

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

### Nightly trip generation — now runs INSIDE the container

`scheduler.sh` and the old host crontab entry are **gone**. The nightly
job — for every active, approved, auto-assign trip plan whose repeat days
include today, create a `DailyTripAssignment` and clone every stop into
daily trip points / household collections — now runs via `cron` installed
*inside* the backend's Docker image:

- **Schedule**: `deploy/cron/generate-daily-trips.cron`, daily at 00:05.
- **Started by**: `deploy/docker-entrypoint.sh`, which starts `cron` in the
  background and gunicorn in the foreground as the container's one process.
- **Env vars**: cron doesn't inherit the container's `--env-file .env`
  values by default, so the entrypoint dumps them to
  `/etc/container_environment.sh`, which the cron job sources before
  running `manage.py`.
- **Logs**: go to the container's stdout/stderr, so `docker compose logs
  backend` shows them — there is no more
  `.../logs/generate_daily_trips.log` file on the host.
- **Manual run** (e.g. to test, or backfill a missed night):
  ```bash
  docker compose exec backend python manage.py generate_daily_trips
  docker compose exec backend python manage.py generate_daily_trips --date 2026-06-26
  ```

Full detail and local test steps: [DEPLOYMENT.md](../DEPLOYMENT.md) §1a
and §3.

## Verifying a deployment

```bash
sudo systemctl status iwms-government-backend.service   # container supervised & up
docker compose logs -f backend                            # gunicorn + cron output

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
| Uploaded images 404 after deploy | `DEBUG=False`, so Django no longer serves `media/` | Check the `./media:/app/media` volume mount in `docker-compose.yml` is present and the path actually has the files |
| OTP / reset mail never arrives | `EMAIL_*` wrong, or SMTP blocks the login | Verify `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`; Gmail needs an app password |
| Push notifications silently never send | `FIREBASE_CREDENTIALS_PATH` unset, or `firebase-admin` not installed | Confirm the path in `.env`, and check `firebase-admin` actually installed (`pyproject.toml` is missing it even though `requirements.txt` has it — see [04](04-commands-reference.md)) |
| Route optimisation fails | `ORS_API_KEY` missing or over quota | Check the key in `.env` |
| No trips generated overnight | Container cron didn't fire — e.g. container was mid-restart at 00:05, or the deploy replaced it around midnight | `docker compose exec backend crontab -l` to confirm the job is installed; `docker compose logs backend` for that night; run `docker compose exec backend python manage.py generate_daily_trips --date <missed-date>` to backfill (idempotent, safe to re-run) |
| A staff member sees zero rows on a list screen they should have access to | No `StaffDataScope` row resolves for them — default-deny, not a bug | Grant them a `StaffDataScope` for the right geography level |
| Tests fail on MySQL specifics | Tests use SQLite in-memory | Expected — see [08](08-unit-testing-guide.md) |

## Reading logs

```bash
journalctl -u iwms-government-backend.service -f   # systemd's view of the container lifecycle
docker compose logs -f backend                       # gunicorn AND the nightly cron job, combined
docker compose logs --since 24h backend | grep generate_daily_trips
```

With `DEBUG=False` Django writes tracebacks to stderr, which Docker
captures as container logs — there's no separate nginx log to check since
nginx isn't part of this stack.

Next: [08-unit-testing-guide.md](08-unit-testing-guide.md).
