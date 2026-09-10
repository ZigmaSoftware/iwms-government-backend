# Local Development

Local dev uses `docker-compose.yml` (no `-f` flag needed) — it runs a
disposable `db` container (`mariadb:11.8`) alongside `backend`. This is
different from production, which has no `db` container at all (see
[02-production-deploy.md](02-production-deploy.md)).

## First-time setup

```bash
cp .env.example .env    # if it exists; otherwise copy a teammate's .env and
                         # adjust — see the key table below
```

Minimum required keys in `.env`: `SECRET_KEY`, `DB_NAME`, `DB_USER`,
`DB_PASSWORD` (also used as the container's root password), `DB_HOST`,
`DB_PORT`. Generate a secret key with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Note: inside the local compose file, `backend`'s `DB_HOST`/`DB_PORT` are
forced to `db`/`3306` regardless of what `.env` says, so it always talks to
the compose-managed container.

## Bring it up

```bash
docker compose up -d              # starts db + backend
docker compose logs -f backend    # watch it come up
```

## Apply migrations

**Why this step exists at all:** `app/migrations/*.py` is gitignored (see
`.gitignore`) — nobody's schema changes travel with `git pull`. Each
machine's `app/migrations/` is its own, local, real migration history.
`docker-compose.yml` bind-mounts your host's `app/migrations/` directory into
the container (`./app/migrations:/app/app/migrations`), so running commands
*inside* the container operates on that real history — not an empty one.

Required the first time, and after pulling any model change from a
teammate:

```bash
docker compose exec -T backend python manage.py makemigrations app
docker compose exec -T backend python manage.py migrate
```

- `makemigrations app` — generates a new migration FILE on your machine's
  `app/migrations/` for any model change that doesn't have one yet. Since
  migration files never travel via git, this is what you run both after
  writing your own model change AND after pulling a teammate's `models.py`
  change (their migration file stayed on their machine — you generate your
  own equivalent locally).
- `migrate` — applies whatever migration files exist (idempotent; safe to
  run repeatedly, a no-op if nothing's pending).

Check what's pending without applying anything:

```bash
docker compose exec -T backend python manage.py showmigrations --plan
```

Optional: seed sample data with `docker compose exec -T backend python
manage.py seed --group <name>` (see `app/management/commands` for available
groups). Seeding is disabled when `DJANGO_ENV=production`.

This is local-only mechanics. Production's migration flow is different (it
runs automatically on every deploy rather than by hand) — see
[02-production-deploy.md](02-production-deploy.md#migrations).

## Check it's healthy

A fresh `db` container starts **empty**, so `401` (auth rejecting an
unauthenticated request — proof Django is up and reached the database) is
the expected healthy response, not `500`:

```bash
curl -o /dev/null -w '%{http_code}\n' http://localhost:9001/api/v1/masters/districts/
```

## Running tests

```bash
docker compose exec -T backend pytest
# or, outside Docker, from a synced venv:
uv run pytest --cov
```

Tests run against SQLite in-memory (`config.test_settings`), not MySQL — a
test passing doesn't guarantee MySQL-specific behavior is correct.

## Tear down

```bash
docker compose down       # stops + removes containers, KEEPS db data (named volume)
docker compose down -v    # also wipes the db volume — fine locally, never do this in prod
```

## Full local reset

```bash
docker compose down -v
docker compose up -d
docker compose exec -T backend python manage.py migrate
```
