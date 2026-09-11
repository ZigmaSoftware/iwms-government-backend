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

This is local-only mechanics. Production's migration flow is different (it
runs automatically on every deploy rather than by hand) — see
[02-production-deploy.md](02-production-deploy.md#migrations).

## Seed sample data

```bash
docker compose exec -T backend python manage.py seed              # everything, in dependency order
docker compose exec -T backend python manage.py seed --group masters   # just one group
```

`--group` is optional — omitting it runs the full `"all"` list. Groups
mostly mirror the URL router group names (`superadmin`, `common-masters`,
`masters`, `waste-types`, `role-assigns`, `user-creations`,
`transport-masters`, `schedule-setup`, `schedule-operations`,
`screen-managements`, `collections`, `customer-masters`,
`complaint-ticket`, `reports`, `driver-demo`, plus a few single-seeder
shortcuts like `scheduler-demo`/`retrip-demo`/`vehicle-breakdowns`) — see
`app/management/commands/seed.py`'s `SEED_GROUPS` dict for the authoritative,
current list and a few legacy aliases (`assets` → `waste-types`,
`schedule-masters` → `schedule-setup` + `schedule-operations`, etc.).

**Order matters within a group and across groups** — e.g. `user-creations`
needs `masters`/`role-assigns` seeded first, `schedule-operations` needs
`schedule-setup`'s collection points to exist. Running the full `seed` (no
`--group`) always gets the order right; running an individual group assumes
its dependencies are already seeded.

**Seeding is blocked outside local dev** — the command refuses to run
unless `DEBUG=True` (and `settings.ENVIRONMENT` isn't `"production"`), both
derived from `DJANGO_ENV` in `.env`. This is a real backend-enforced guard,
not just a convention — the command exits immediately with an error message
rather than seeding a production database by accident.

## Poke around the database

Open an interactive MySQL shell inside the `db` container:

```bash
docker compose exec db mariadb -u root -p iwmsdbGovernment
```

Prompts for the password — use `DB_PASSWORD` from `.env`, or skip the
prompt entirely:

```bash
docker compose exec db mariadb -u root -p"$(grep DB_PASSWORD .env | cut -d= -f2)" iwmsdbGovernment
```

Once inside:

```sql
SHOW TABLES;                                       -- list every table
DESCRIBE app_staffcreationofficedetails;            -- a table's columns
SELECT * FROM app_staffcreationofficedetails LIMIT 10;  -- peek at rows
EXIT;
```

Or run a one-off query straight from the host, without an interactive
shell:

```bash
docker compose exec -T db mariadb -u root -p"$(grep DB_PASSWORD .env | cut -d= -f2)" iwmsdbGovernment -e "SHOW TABLES;"
```

phpMyAdmin (`192.168.1.128/phpmyadmin`) gives the same access through a
browser UI if you'd rather click through tables than use the CLI.

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
