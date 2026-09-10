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
