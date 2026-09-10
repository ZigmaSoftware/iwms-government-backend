# Production Deployment

## What happens on push to `main`

Pushing to `main` (or a manual "Run workflow" dispatch) triggers a
**self-hosted runner** on the production server itself (`.github/workflows/deploy.yml`).
GitHub's cloud runners can't reach this server — only ports 3000/9001/80 are
forwarded, and 22 is not — so a self-hosted runner polling GitHub outbound is
the only option. This also means the image is built on the server; GHCR is
not part of the deploy path.

In order, the workflow:

1. Checks out the new commit into the runner's own workspace and builds the
   Docker image there.
2. Syncs the separate, persistent deployment clone at
   `/home/admin/localserver/iwmsGovernment/iwms-government-backend` to the
   same commit (`git fetch` + `git checkout --force`).
3. Smoke-tests the new image against the **external host database** using
   `--network host` (mirroring `docker-compose.prod.yml`) — fails loudly
   before touching the live service if the image can't reach MySQL.
4. Restarts the service: `sudo systemctl restart iwms-government-backend`,
   which runs `docker compose -f docker-compose.prod.yml up --remove-orphans`
   under systemd.
5. Runs `makemigrations` then `migrate` **inside** the running container —
   safe because the container bind-mounts the server's real, persistent
   `app/migrations/`, so this only ever adds incremental files.
6. Collects static files, double-checks for unapplied migrations (should
   always be zero now), and polls the API until it answers `200/401/403`.
7. Prunes dangling images.

Pushes to `dev` or any other branch do nothing — the workflow doesn't even
start.

### There are TWO checkouts, not one — this is the part people misread

The workflow never runs `git pull` on the live deployment. It juggles two
**separate, unrelated directories** on the same machine:

| | Runner's own workspace | The deployment clone |
|---|---|---|
| Path | Inside `actions-runner-backend/_work/...` | `/home/admin/localserver/iwmsGovernment/iwms-government-backend` |
| Created by | `actions/checkout@v4` (step 1), fresh every run | An existing git clone that must already exist — step 2 only `fetch`/`checkout`s it, it never `git clone`s from scratch |
| Has `.env`, `media/`, `static/`? | No — a bare checkout, nothing else | Yes — this is the only place these live |
| What happens to it | `docker build .` runs here — this is *only* a build context | `git fetch` + `git checkout --force` (step 2) moves it to the new commit; `docker compose` always runs from here |

So "restart the production server" does **not** mean "go fetch and rebuild
from scratch." By the time step 4 (`systemctl restart`) runs:

- the new image already exists locally, tagged `ghcr.io/zigmasoftware/iwms-government-backend:latest` (from step 1's `docker build`, run without `--pull`/`push` — it never touches GHCR, just tags the image on this machine),
- the deployment clone's `docker-compose.prod.yml` already points at `image: ...:latest`,
- so `systemctl restart` → `docker compose -f docker-compose.prod.yml up --remove-orphans` sees that `:latest` now refers to a different image than the currently-running container, stops the old container, and starts a new one from the new image — using the `.env`/volumes that only exist in the deployment clone.

**Who's "managing Docker" here?** Nothing beyond what's in `deploy.yml` and
the systemd unit — there is no separate orchestrator (no Kubernetes, no
Watchtower, no swarm). The self-hosted runner *is* a process on this exact
server, so the workflow's `run:` steps are just shell commands executing
directly on the machine — `docker build`, `docker run`, `docker compose`,
`systemctl` — the same as if you'd typed them yourself over SSH. systemd's
only job is to keep the `docker compose up` process supervised (restart it
if it crashes, via `Restart=always`) — it doesn't initiate deploys on its
own; CI triggers it by calling `systemctl restart`.

## Migrations

Unlike local dev (where you run `makemigrations`/`migrate` by hand — see
[01-local-dev.md](01-local-dev.md)), **production applies migrations
automatically on every deploy**, as step 5 of the workflow above. No one
needs to log into the server and run a command for a routine schema change
to go live.

Why this is safe to fully automate here, when it wouldn't be safe in a
plain CI checkout: `app/migrations/*.py` is gitignored, so a bare checkout
has an empty migrations folder — but `docker-compose.prod.yml` bind-mounts
the **server's own real, persistent** `app/migrations/` directory into the
container. So `makemigrations` running inside that container sees the true
history and only ever adds new incremental files for whatever model change
just got deployed; it never regenerates history from scratch. `migrate` is
idempotent on top of that — applying an already-applied migration is a
no-op.

The exact commands the workflow runs (also useful to run by hand if you
ever need to force a migration outside of a deploy):

```bash
docker compose -f docker-compose.prod.yml exec -T backend python manage.py makemigrations --noinput
docker compose -f docker-compose.prod.yml exec -T backend python manage.py migrate --noinput
```

To check whether anything is pending without applying it:

```bash
docker compose -f docker-compose.prod.yml exec -T backend python manage.py showmigrations --plan
```

## The compose-file split

- `docker-compose.yml` — **local dev only**. Runs `db` (mariadb:11.8) +
  `backend`.
- `docker-compose.prod.yml` — **production only**. Runs `backend` ONLY —
  there is no `db` container in production. It connects instead to the
  externally-managed MySQL/MariaDB already running on the host (the same one
  phpMyAdmin administers).

Production uses `network_mode: host` (not `host.docker.internal`) because
the host MariaDB is locked down two ways at once — it binds `127.0.0.1`
only, and the DB user is granted for `'root'@'localhost'` only — so a
bridged container's connection is refused twice over; host networking makes
the container share the host's loopback, satisfying both restrictions
without loosening either. One consequence: `ports:` is not used in prod
(illegal under `network_mode: host`) — gunicorn just binds `0.0.0.0:9001`
inside the image, and Apache reverse-proxies to `127.0.0.1:9001` as before.

Always pass `-f docker-compose.prod.yml` explicitly for any production
command — there is no default that happens to be correct for prod. A bare
`docker compose ...` with no `-f` talks to the local dev file.

## systemd

`deploy/systemd/iwms-government-backend.service` runs `docker compose -f
docker-compose.prod.yml up --remove-orphans` in the foreground so systemd
tracks it and `Restart=always` works. `deploy/` is **gitignored** — the
installed unit at `/etc/systemd/system/` is a manual copy, not something CI
touches.

**Gotcha:** editing the unit file in the repo does nothing by itself. You
must reinstall it:

```bash
sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart iwms-government-backend
```

Forgetting this step is the most common way "I fixed the unit file" turns
into "nothing changed" — the installed copy and the repo copy silently
drift apart otherwise.

## Manual command equivalents

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
sudo systemctl restart iwms-government-backend
docker compose -f docker-compose.prod.yml exec -T backend python manage.py makemigrations --noinput
docker compose -f docker-compose.prod.yml exec -T backend python manage.py migrate --noinput
docker compose -f docker-compose.prod.yml exec -T backend python manage.py collectstatic --noinput
docker compose -f docker-compose.prod.yml ps      # confirm: backend only, NO db container
curl -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9001/api/v1/masters/districts/
```

If `ps` ever shows a `db` container in production, something has regressed
to the old (abandoned) containerized-DB setup — it should never exist there.

## Logs

```bash
journalctl -u iwms-government-backend.service -f
docker compose -f docker-compose.prod.yml logs -f backend
```
