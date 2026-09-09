# 11 — Server Deploy: from the `sathya` branch to production

This file is the actual, step-by-step process to get code that currently
only exists on your local `sathya` branch running live on the production
server (`192.168.1.128`, public IP `115.245.93.26`). Test locally first —
see [10-local-docker-testing.md](10-local-docker-testing.md) — then follow
this.

If you only remember one thing: **nothing you do on `sathya` reaches
production by itself.** The GitHub Actions workflow
([.github/workflows/deploy.yml](../.github/workflows/deploy.yml)) triggers
**only** on a push landing on `main`:

```yaml
on:
  push:
    branches: [main]
```

Pushing `sathya`, or even opening a PR, triggers nothing. Only the moment a
push (including a PR merge) lands on `main` does anything deploy.

## The full path, step by step

### 1. Confirm where you stand

```bash
cd iwms-government-backend
git status
git log --oneline origin/sathya..sathya   # commits that exist locally but not on GitHub yet
```

### 2. Push `sathya` to GitHub

```bash
git push origin sathya
```

Nothing runs yet — `sathya` is invisible to the workflow.

### 3. Open a Pull Request: `sathya` → `main`

On GitHub, open the PR for this repo. This is the review checkpoint before
anything reaches the real server. No workflow fires on the PR itself either
(the workflow only listens for `push` on `main`, not `pull_request`).

Per [05-team-workflow.md](05-team-workflow.md)'s checklist, before opening
the PR:

- [ ] `git status` shows only source files you meant to change
- [ ] No `.env`, no `__pycache__`, no `coverage.xml`
- [ ] No credentials, tokens, IPs or passwords in the code or comments
- [ ] `python -m pytest tests/ -q` passes
- [ ] If your change needs new reference data, the PR description names the
      `seed --group` to run — seeding is still a manual step (schema
      migrations are now automatic, see step 5 below, but seeders are not)

### 4. Merge the PR into `main`

The merge commit lands on `main` → GitHub fires a `push` event → the
self-hosted runner (already running on `192.168.1.128`, continuously polling
GitHub over outbound HTTPS) picks up the job. See
[09-docker-cutover-2026-09-08.md](09-docker-cutover-2026-09-08.md) for why a
self-hosted runner is required at all: the router only forwards ports
`3000`/`9001`/`80` inbound — not `22` — so GitHub's own cloud runners cannot
reach in to deploy; the runner polling *outward* is what makes this work
without opening SSH.

### 5. What the workflow does automatically, in order

Reading [.github/workflows/deploy.yml](../.github/workflows/deploy.yml)
top to bottom:

```bash
# 1. Checkout — actions/checkout@v4 pulls the exact commit just merged
#    into the runner's own working directory (NOT the deployment directory
#    below — those are two separate paths, see step 6).

# 2. Build the image, right there on the server
docker build \
  -t ghcr.io/zigmasoftware/iwms-government-backend:<commit-sha> \
  -t ghcr.io/zigmasoftware/iwms-government-backend:latest \
  .

# 3. Ensure the "db" container exists — create if missing, reuse if present.
#    Never recreates or wipes an existing db container/volume.
docker compose up -d db

# 4. Smoke-test the freshly built image against that db, BEFORE touching
#    the live service — fails loudly here rather than after restart if the
#    new image can't reach the database.
docker run --rm --env-file .env --network <compose-network> \
  -e DB_HOST=db -e DB_PORT=3306 \
  ghcr.io/zigmasoftware/iwms-government-backend:<commit-sha> \
  python -c "... SELECT DATABASE() ..."

# 5. Restart the live service
sudo systemctl restart iwms-government-backend

# 6. Apply database migrations — automatic, every deploy (see step 7 below
#    for why this is now safe to run unattended)
docker compose exec -T backend python manage.py migrate --noinput

# 7. Collect static files inside the now-running container
docker compose exec -T backend python manage.py collectstatic --noinput

# 8. Sanity check — should always report 0 pending migrations now that
#    step 6 runs automatically; a non-zero count means investigate
docker compose exec -T backend python manage.py showmigrations --plan

# 9. Health check — poll until the API answers 200/401/403
curl http://127.0.0.1:9001/api/v1/masters/districts/

# 10. Clean up dangling images
docker image prune -f
```

You do **not** SSH in and run any of this by hand — it all happens
automatically once the merge lands on `main`, **including schema
migrations now** (this changed after this doc was first written — see
step 7 for the details).

### 6. The two directories on the server — don't confuse them

- **The runner's own checkout** — ephemeral, git-pulled fresh every run by
  `actions/checkout@v4`. `docker build` runs from here.
- **`/home/admin/localserver/iwmsGovernment/iwms-government-backend`** —
  the live deployment directory: holds the real `.env`, `media/`, `static/`,
  and `docker-compose.yml`. The workflow only `cd`s here to run
  `docker compose` / `systemctl` commands against the already-built
  `:latest` image — this directory is never itself git-pulled.

### 7. Schema migrations — now automatic, here's why it's safe

Migrations are gitignored (`.gitignore` excludes `**/migrations/*`), so a
**bare CI checkout** has an empty `app/migrations/` — running `migrate`
against that directly would fail with
`ValueError: Dependency on app with no migrations: app`. That used to be
the reason migrations stayed a manual, SSH-in-yourself step.

That's no longer the actual constraint, though: `docker-compose.yml`
bind-mounts the server's real, persistent migration files into the running
container (`./app/migrations:/app/app/migrations`), so
`docker compose exec backend python manage.py migrate` runs **inside the
container**, against the real migration history already on the server —
never against the checkout's empty one. The workflow now runs exactly that
command automatically, every deploy, right after the service restart.

This is safe to automate because Django's `migrate` is **idempotent** — it
only applies migrations that haven't run yet and is a no-op otherwise.
Running it on a deploy that has no schema changes just prints
`No migrations to apply.` and moves on. It does **not** run
`makemigrations` — generating new migration files is still a developer
action, done locally before committing, per
[05-team-workflow.md](05-team-workflow.md). CI only ever applies migration
files that already exist on the server; it never creates new ones.

**What is still manual:** seeding new reference data
(`manage.py seed --group <group>`) — say which group in your PR
description, and run it yourself on the server after the deploy, same as
before.

### 8. Confirm the deploy actually worked

From anywhere (port 9001 is forwarded to the public IP):

```bash
curl -o /dev/null -w "%{http_code}\n" http://115.245.93.26:9001/api/v1/masters/districts/
```

`401`/`403` = healthy. `000` = nothing listening — check
`sudo systemctl status iwms-government-backend` on the server.
`500` = the API is up but can't reach the database.

Or, with GitHub CLI / the Actions tab on the repo, check the actual run's
logs — that is the ground truth for whether each step passed.

## First deploy after the db-container change — extra care needed

Before this document existed, `docker-compose.production.yml` used
`network_mode: host` and had no `db` service — the backend talked directly
to a MariaDB installed on the server's own OS
(`DB_HOST=localhost`), which holds the **real, existing production data**.

The renamed `docker-compose.yml` now runs its own `db` container instead
(`DB_HOST=db`). On the **first** deploy after this change reaches `main`:

- `docker compose up -d db` will find no existing `db` container, so it
  creates a brand-new one — **empty**, no historical data.
- The old host-installed MariaDB is untouched and still has the real data,
  it's just no longer what the app talks to.

**This is deliberate and matches the "create if missing, reuse if present,
never auto-migrate data" decision made for this change** — see
[10-local-docker-testing.md](10-local-docker-testing.md)'s note on this
too. Migrating the real data across is a separate, manual step:

```bash
# On the server, BEFORE or shortly after this deploy — take a dump of the
# real data from the old host MariaDB:
mysqldump -h localhost -u root -p iwmsdbGovernment > iwmsdbGovernment_backup.sql

# Then restore it into the new db container:
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
docker compose exec -T db mariadb -u root -p iwmsdbGovernment < iwmsdbGovernment_backup.sql
```

Do this deliberately, with a verified backup, not as an unattended part of
a routine deploy. Confirm row counts match between the old host database and
the new container before considering the migration done.

## Quick reference — the whole flow in one glance

```text
  your machine (sathya)
        │  git push origin sathya
        ▼
  origin/sathya (GitHub)
        │  open PR: sathya -> main
        │  review, checklist, merge
        ▼
  main (GitHub)
        │  push event fires automatically
        ▼
  self-hosted runner on 192.168.1.128
        │  checkout -> build -> ensure db -> smoke-test
        │  -> systemctl restart -> migrate (automatic)
        │  -> collectstatic -> sanity-check pending migrations
        │  -> health check
        ▼
  live at http://115.245.93.26:9001  (and :3000 for frontend)

  Manual, NOT automated by the workflow:
    - makemigrations (generating new migration files — still a developer
      action, done locally before committing; migrate applying them on
      the server IS automatic now)
    - seeding new reference data (`manage.py seed --group <group>`)
    - first-time data migration from the old host MariaDB into the new
      `db` container (mysqldump / restore, see above)
```
