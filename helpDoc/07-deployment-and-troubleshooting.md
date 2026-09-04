# 07 — Deployment and Troubleshooting

## First-time setup on a server

```bash
# 1. Get the code
git clone <repo-url> iwms-government-backend && cd iwms-government-backend

# 2. Python environment
uv venv && source .venv/bin/activate && uv sync
# or, on the actual deploy server:
./server_uv_sync.sh

# 3. Settings — fill in real values, and set DJANGO_ENV=production
#    (no .env.example exists yet — see 02 and 06 — ask a teammate for a
#    working .env or rebuild one from the key table in 02)
nano .env

# 4. Database (see 02-database-and-env.md for the SQL)
python3 manage.py makemigrations app
python3 manage.py migrate

# 5. Static files and an admin login
python3 manage.py collectstatic --noinput
python3 manage.py createsuperuser

# 6. Sanity check, then run
python3 manage.py check --deploy
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
production. Use gunicorn (already a pinned dependency, `gunicorn==23.0.0`):

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Put nginx in front to terminate TLS and serve `/static/` and `/media/` from
disk. Keep gunicorn alive with a systemd unit so it restarts on boot and on
crash — this repo does not ship a systemd unit file, so that part is
per-server configuration, not something to look for here.

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

Unlike the private backend, this repo has no `cron.sh` checked in (though
`scheduler.sh`'s header comment references one existing on the deploy
server itself). What's here instead:

- **`manage.sh`** — thin wrapper around `manage.py`: uses
  `.venv/bin/python manage.py "$@"` if a venv exists, else falls back to
  `uv run python manage.py "$@"`. Use this instead of remembering whether a
  venv is active.
- **`scheduler.sh`** — the nightly trip-generation entry point. For every
  active, approved, auto-assign trip plan whose repeat days include today,
  it creates a `DailyTripAssignment` and clones every stop into daily trip
  points / household collections. Wired into the server's crontab to run at
  12:05 AM. It hardcodes the deploy path
  `/home/admin/localserver/iwmsGovernment/iwms-government-backend` and logs
  to `.../logs/generate_daily_trips.log`. Its Python-binary fallback chain
  is worth knowing about if trips silently stop generating: it tries
  `.venv/bin/python`, then `venv/bin/python`, then a **legacy path pointing
  at the private backend's venv** (leftover from when this project was
  bootstrapped alongside `iwms-backend`), then `/usr/bin/python3`. If none
  of those actually have the right dependencies installed, the job will run
  against the wrong interpreter without an obvious error — check the log
  file first.
- **`server_uv_sync.sh`** — wraps `uv sync --locked` for deploys, with a DNS
  reachability check and a note to fall back to reusing the (legacy,
  private-backend-named) venv if the server is offline for package
  downloads.

## Verifying a deployment

```bash
curl -i http://<host>:8000/                       # confirms the server answers
curl -i http://<host>:8000/api/v1/                # the grouped API index
```

Then open `http://<host>:8000/api/v1/swagger/` and try a real login through
it. A successful login returning both an access token and a refresh token
proves the database, settings, `SECRET_KEY` and JWT config are all working
together — see [01](01-architecture-overview.md) for why there are two
tokens here.

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
| Uploaded images 404 after deploy | `DEBUG=False`, so Django no longer serves `media/` | Serve `media/` from nginx |
| OTP / reset mail never arrives | `EMAIL_*` wrong, or SMTP blocks the login | Verify `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`; Gmail needs an app password |
| Push notifications silently never send | `FIREBASE_CREDENTIALS_PATH` unset, or `firebase-admin` not installed | Confirm the path in `.env`, and check `firebase-admin` actually installed (`pyproject.toml` is missing it even though `requirements.txt` has it — see [04](04-commands-reference.md)) |
| Route optimisation fails | `ORS_API_KEY` missing or over quota | Check the key in `.env` |
| No trips generated overnight | `generate_daily_trips` / `scheduler.sh` didn't run, or its Python fallback resolved to the wrong venv | Check `.../logs/generate_daily_trips.log`; run `python3 manage.py generate_daily_trips` manually |
| A staff member sees zero rows on a list screen they should have access to | No `StaffDataScope` row resolves for them — default-deny, not a bug | Grant them a `StaffDataScope` for the right geography level |
| Tests fail on MySQL specifics | Tests use SQLite in-memory | Expected — see [08](08-unit-testing-guide.md) |

## Reading logs

```bash
journalctl -u <your-gunicorn-unit> -f     # if running under systemd
tail -f /var/log/nginx/error.log          # nginx-level failures
tail -f .../logs/generate_daily_trips.log # the nightly scheduler job
```

With `DEBUG=False` Django writes tracebacks to stderr, which systemd
captures. If you see nginx return 502, the traceback is in the gunicorn
journal, not in nginx's log.

Next: [08-unit-testing-guide.md](08-unit-testing-guide.md).
