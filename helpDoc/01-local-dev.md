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

Required the first time, and after pulling any model change from a teammate
— migrations are gitignored, so nobody's schema changes travel with `git
pull`. The container mounts the host's real `app/migrations/`, so this uses
your actual migration history:

```bash
docker compose exec -T backend python manage.py makemigrations app
docker compose exec -T backend python manage.py migrate
```

Optional: seed sample data with `docker compose exec -T backend python
manage.py seed --group <name>` (see `app/management/commands` for available
groups). Seeding is disabled when `DJANGO_ENV=production`.

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
