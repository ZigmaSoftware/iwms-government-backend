# 10 — Local Docker Testing (frontend + backend + db, 3 containers)

This is the local counterpart to
[11-server-deploy-from-sathya.md](11-server-deploy-from-sathya.md). Use this
file to stand up the whole stack — frontend, backend, **and** database — as
three separate Docker containers on your own machine, and to prove the exact
mechanism GitHub Actions relies on (`docker compose up -d db` never wiping an
existing database) actually behaves the way it's supposed to, **before**
trusting it on the real server.

If you only remember one thing: **`docker-compose.yml` now defines three
services — `db`, `backend` — in this repo, plus the separate frontend repo's
own `docker-compose.yml` for the third.** There is no more
`docker-compose.production.yml`; it was renamed to `docker-compose.yml` (see
[09-docker-cutover-2026-09-08.md](09-docker-cutover-2026-09-08.md) for the
original cutover, and the "What changed after the cutover" note at the
bottom of this file for the db-container change specifically).

## The 3 containers, at a glance

| Container | Compose file | Image | Reachable at |
|---|---|---|---|
| `iwms-government-backend-db-1` | `iwms-government-backend/docker-compose.yml` | `mariadb:11.8` | internal only — hostname `db`, port `3306`, from inside the compose network |
| `iwms-government-backend-backend-1` | `iwms-government-backend/docker-compose.yml` | built from this repo's `Dockerfile` | `http://localhost:9001` |
| `iwms-government-frontend-frontend-1` | `iwms-government-frontend/docker-compose.yml` | built from the frontend repo's `Dockerfile` | `http://localhost:3000` |

They are **not** one container running three programs — each has its own
image, its own container ID, its own process tree. `backend` reaches `db`
purely through Docker's internal DNS on the compose network (the hostname
`db` only resolves inside that network); nothing routes through your
machine's own `localhost`.

## Prerequisites

```bash
docker --version
docker compose version
```

You do **not** need a host-installed MariaDB for this — that was the old
architecture (`network_mode: host` + `DB_HOST=localhost`). The new
`docker-compose.yml` runs its own `db` container instead.

Your `.env` (in `iwms-government-backend/`) needs at least:

```bash
DB_ENGINE=django.db.backends.mysql
DB_NAME=iwmsdbGovernment
DB_USER=root
DB_PASSWORD=<something>
# DB_HOST / DB_PORT here are irrelevant to the container path — docker-compose.yml
# forces DB_HOST=db, DB_PORT=3306 regardless of what .env says, so backend
# always talks to the compose-managed db container, never a stray host value.
```

## Step-by-step: bring the backend + db up

```bash
cd iwms-government-backend

# 1. Clean slate (safe — does NOT delete the db's data volume, see below)
docker compose down

# 2. Bring db + backend up
docker compose up -d
docker compose ps
```

Expect `db` to show `Up ... (healthy)` and `backend` to show `Up`. **On a
truly first-ever boot, `db`'s healthcheck can take longer than `backend`'s
first `depends_on` wait**, and you'll see:

```
Container iwms-government-backend-db-1  Error dependency db failed to start
dependency failed to start: container iwms-government-backend-db-1 is unhealthy
```

This is not a real failure — MariaDB was still finishing initialization.
Just re-run:

```bash
docker compose up -d
```

Compose picks up where it left off; once `db` reports healthy, `backend`
starts immediately. (This is exactly the same retry loop the CI workflow's
"Ensure the database container exists" step performs automatically — see
[11](11-server-deploy-from-sathya.md).)

## Confirm the API is actually working (not just "container running")

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:9001/api/v1/masters/districts/
```

| Code | Meaning |
|---|---|
| `401` or `403` | **Healthy.** Django booted and reached the database — an auth-protected endpoint correctly rejecting an unauthenticated request proves both. |
| `000` | Nothing listening — container didn't start, or crashed. Check `docker compose logs backend`. |
| `500` | Django is up but the database call failed — check `DB_HOST`/`DB_PORT`/credentials, or `docker compose logs db`. |

## Apply migrations (the db container starts empty)

A freshly created `db` container has no schema at all — migrations are
gitignored (see [02-database-and-env.md](02-database-and-env.md)), so they
must be applied inside the container, same as any other machine:

```bash
docker compose exec -T backend python manage.py migrate
```

Confirm everything applied:

```bash
docker compose exec -T backend python manage.py showmigrations --plan | tail -20
```

Every line should show `[X]`. Any `[ ]` means that migration hasn't run yet.

## Prove backend is really talking to the `db` container

```bash
docker compose exec db mariadb -u root -p"$(grep DB_PASSWORD .env | cut -d= -f2)" -e "SHOW DATABASES;"
```

You should see `iwmsdbGovernment` (or whatever `DB_NAME` is set to) in the
list — created by the `MARIADB_DATABASE` env var on the `db` service the
first time it booted.

## Bring the frontend up too (separate repo, separate compose file)

```bash
cd ../iwms-government-frontend
docker compose build     # only needed after an .env change — see the file's own comment: VITE_* is baked in at build time, not read at runtime
docker compose up -d
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:3000/
```

`200` = frontend serving. Point your browser at `http://localhost:3000` to
see it for real.

## The safety property CI/CD depends on — test it yourself

The whole reason `db` is safe to add to the production workflow is that
`docker compose up -d db` is **idempotent**: run it again against an
already-running, already-populated `db`, and Compose does nothing
destructive — no recreate, no data loss. Prove this to yourself locally
before trusting it against real production data:

```bash
# 1. Add a marker row so you have something to check for
docker compose exec db mariadb -u root -p"$(grep DB_PASSWORD .env | cut -d= -f2)" \
  -e "USE iwmsdbGovernment; CREATE TABLE IF NOT EXISTS _test_marker (id INT); INSERT INTO _test_marker VALUES (1);"

# 2. Re-run the exact command the workflow runs
docker compose up -d db

# 3. Confirm the marker survived — an empty result here would mean data was lost
docker compose exec db mariadb -u root -p"$(grep DB_PASSWORD .env | cut -d= -f2)" \
  -e "USE iwmsdbGovernment; SELECT * FROM _test_marker;"

# 4. Clean up the marker
docker compose exec db mariadb -u root -p"$(grep DB_PASSWORD .env | cut -d= -f2)" \
  -e "USE iwmsdbGovernment; DROP TABLE _test_marker;"
```

If step 3 still shows the row, `up -d db` is confirmed non-destructive on an
existing container — exactly the property the production deploy step relies
on.

## Tearing down

```bash
# Stops + removes containers, KEEPS the db's data (named volume survives)
docker compose down

# Only if you deliberately want to wipe local test data too — irreversible
docker compose down -v
```

Never run `docker compose down -v` against anything that might be pointed at
real data. Locally that's unlikely, but the same command against a
misconfigured production `.env` would delete real rows — this is exactly why
[11](11-server-deploy-from-sathya.md)'s CI step only ever uses
`up -d db`, never `down` or `--force-recreate`.

## Full local reset, start to finish

```bash
cd iwms-government-backend
docker compose down -v                      # wipe everything, including data
docker compose up -d                        # recreate db + backend fresh
# if backend failed to start because db wasn't healthy yet, just re-run:
docker compose up -d
docker compose exec -T backend python manage.py migrate
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:9001/api/v1/masters/districts/
```

## What changed after the original Docker cutover

[09-docker-cutover-2026-09-08.md](09-docker-cutover-2026-09-08.md) documents
the original move to Docker, where the compose file was named
`docker-compose.production.yml`, used `network_mode: host`, and had **no**
`db` service — the backend connected to a MariaDB installed directly on the
host OS (`DB_HOST=localhost`). That file was later renamed to
`docker-compose.yml` and a `db` service (`mariadb:11.8`, named volume
`iwms_gov_db`) was added, moving `backend` off host networking and onto the
default compose network with `DB_HOST=db`. The host-installed MariaDB still
exists and still holds the real historical data — migrating that data into
the new `db` container is a deliberate, manual, one-time step (not done by
this file or by CI/CD), covered in
[11-server-deploy-from-sathya.md](11-server-deploy-from-sathya.md).

Older commands in [07](07-deployment-and-troubleshooting.md) and
[09](09-docker-cutover-2026-09-08.md) that still say
`docker compose -f docker-compose.production.yml ...` should be read as
`docker compose ...` (no `-f` needed — `docker-compose.yml` is now the
default filename `docker compose` looks for automatically) — those files
have not been rewritten yet, so mentally substitute the new filename when
following them.
