# 12 — Server Permissions (`admin` vs `iwmsuser`) and Docker Commands

Two things live in this file:

1. **Who owns what on the server**, and why the deploy broke on 2026-09-09
   when the installed systemd unit went stale.
2. **A Docker command reference** for this stack — the day-to-day commands,
   using the current `docker-compose.yml` filename.

If you only remember one thing:

> **There are TWO Linux accounts in play. You log in as `admin`; the GitHub
> Actions runner executes as `iwmsuser`. What works when you type it by hand
> does NOT prove it works in CI — `admin` has full `sudo`, `iwmsuser` has a
> deliberately narrow allow-list. Always test runner behaviour with
> `sudo -n` after `sudo -k`.**

---

## The two accounts

| | `admin` | `iwmsuser` |
|---|---|---|
| uid | 1000 | 1007 |
| What it is | The human login (you, over SSH/VS Code) | The service account the Actions runner runs as |
| `sudo` | `(ALL : ALL) ALL` — unrestricted root | Only the exact commands in `deploy/sudoers/iwms-runner` |
| `docker` group | yes | yes |
| In group `iwmsuser` | yes | yes (primary) |

`admin` being in the `iwmsuser` group is what makes the shared project tree
work: everything is group-owned by `iwmsuser` and group-writable, so both
accounts can read and write the same files.

### Ownership of the project tree

Verify at any time with:

```bash
cd /home/admin/localserver/iwmsGovernment
stat -c '%U:%G %A %n' iwmsGovernment iwmsPrivate \
  iwms-government-backend iwms-government-frontend \
  iwms-government-backend/{static,media,.git} \
  actions-runner-backend actions-runner-frontend
```

The intended state:

| Path | Owner:Group | Mode | Notes |
|---|---|---|---|
| `iwmsGovernment/`, `iwmsPrivate/` | `admin:iwmsuser` | `drwxrwsr-x` | setgid — new files inherit group `iwmsuser` |
| both project dirs, `.git/`, `media/`, `static/` | `admin:iwmsuser` | `drwxrwsr-x` | both accounts read+write |
| `actions-runner-*/` | `iwmsuser:iwmsuser` | `drwxrwsr-x` | runner owns them; `admin` writes via group |
| `actions-runner-*/.credentials` | `iwmsuser:iwmsuser` | `-rw-r-----` | **secret** — runner registration token |
| `actions-runner-*/.credentials_rsaparams` | `iwmsuser:iwmsuser` | `-rw-------` | **secret** — runner private RSA key |

The `s` in `drwxrwsr-x` (setgid) matters: without it, files created by
`admin` get group `admin` and `iwmsuser` silently loses write access later.

### Repairing permissions

If a directory ends up wrongly owned — most often because **Docker created
it as root via a bind mount**, which is exactly what happened to `static/`:

```bash
cd /home/admin/localserver/iwmsGovernment

# Shared project tree: group-owned by iwmsuser, group-writable, setgid
sudo chgrp -R iwmsuser <path>
sudo chmod -R g+w      <path>
sudo find <path> -type d -exec chmod g+s {} +
```

For the runner directories specifically, re-tighten the secrets afterwards —
a blanket `chmod -R g+w` would leave the runner's private key group-writable:

```bash
sudo chmod 600 actions-runner-{backend,frontend}/.credentials_rsaparams
sudo chmod 640 actions-runner-{backend,frontend}/.credentials
```

> **Why this matters:** anyone who can read those two files can impersonate
> your self-hosted runner to GitHub. They are the one thing in the tree that
> should *not* be widely readable.

### Testing as the runner, not as yourself

This is the trap that cost time on 2026-09-09. `admin` has blanket `sudo`,
so once you have typed your password, a **cached sudo timestamp** makes
almost anything succeed for the next few minutes — including commands the
runner would be refused. Clear the timestamp first:

```bash
sudo -k                                                  # drop cached credential
sudo -n /usr/bin/systemctl is-active iwms-government-backend    # -> active
sudo -n /usr/bin/systemctl is-active --quiet iwms-government-backend
#   -> sudo: a password is required     (NOT in the allow-list)
```

`deploy/sudoers/iwms-runner` grants **exact command strings, no wildcards**.
`is-active` is allowed; `is-active --quiet` is a different string and is
therefore denied. On the runner there is no interactive fallback, so a
command like that fails the deploy outright.

---

## The systemd unit is server-only — and can go stale

`.gitignore` excludes `deploy/systemd/`:

```gitignore
# === Server-only systemd unit files (never commit — install manually on server) ===
deploy/systemd/
```

Consequences to internalise:

- `git checkout ... -- deploy/systemd/...` **fails** with
  `error: pathspec ... did not match any file(s) known to git`. That is
  expected, not a problem — git has no copy.
- CI cannot sync the unit. The copy at `/etc/systemd/system/` is
  authoritative, and nothing detects it drifting from `deploy/systemd/`.

### The 2026-09-09 failure, end to end

`docker-compose.production.yml` was renamed to `docker-compose.yml`, but the
**installed** unit still said `-f docker-compose.production.yml`:

1. `systemctl restart` returned success in ~1s. The unit is `Type=simple`,
   so systemd only confirms the process **spawned**, not that it works.
   The deploy step went green.
2. Behind it, `docker compose -f docker-compose.production.yml up` died with
   `no configuration file provided: not found`, and `Restart=always` put the
   unit into a 5-second crash loop.
3. The migrations step waited 30× for `docker compose exec -T backend`, then
   failed with the *misleading* error **`service "backend" is not running`**.

The real cause was three steps earlier. Fix:

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart iwms-government-backend
systemctl status iwms-government-backend --no-pager
```

Then verify it actually **stayed** up — the whole point of the incident:

```bash
sleep 5 && systemctl is-active iwms-government-backend    # must print: active
```

> **Note:** the unit's `ExecStartPre` runs `docker compose down
> --remove-orphans`, which stops **both** containers including `db`, and
> removes the network. That is safe — `iwms_gov_db` is a *named volume* and
> plain `down` never deletes those (only `down -v` would). But every service
> restart does briefly drop the database container.

### Checking for drift before it bites

```bash
diff -u /etc/systemd/system/iwms-government-backend.service \
        deploy/systemd/iwms-government-backend.service \
  && echo "installed unit is up to date"
```

Run this whenever a deploy fails strangely. Empty output = in sync.

---

# Docker commands for this stack

Full basics — kill/recreate, images, disk cleanup, common mistakes — are in
[09-docker-cutover-2026-09-08.md](09-docker-cutover-2026-09-08.md#docker-basics-for-these-two-services).
This section is the **current-filename** quick reference: the compose file is
now plain `docker-compose.yml`, so **no `-f` flag is needed**. Older docs
still show `-f docker-compose.production.yml` — that file no longer exists.

All commands assume:

```bash
cd /home/admin/localserver/iwmsGovernment/iwms-government-backend
```

### Status and health

```bash
docker compose ps              # running containers
docker compose ps -a           # includes stopped/exited ones — use when something is missing
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Is the API actually serving? 401 = healthy (auth rejecting an
# unauthenticated request proves Django ran AND reached MySQL).
# 000 = nothing listening. 500 = database problem.
curl -s -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:9001/api/v1/masters/districts/
```

### Start / stop / restart

Prefer systemd on this server — it owns the containers:

```bash
sudo systemctl restart iwms-government-backend
sudo systemctl stop    iwms-government-backend
sudo systemctl status  iwms-government-backend --no-pager
```

Direct compose (bypasses systemd — fine for debugging):

```bash
docker compose up -d           # start/create in background
docker compose restart backend # restart just the app, leave db alone
docker compose down            # stop + remove containers (named volume SAFE)
```

> **Never run `docker compose down -v` on this server.** The `-v` deletes the
> `iwms_gov_db` named volume — that is the production database.

### The database container

```bash
docker compose up -d db        # idempotent: creates only if MISSING, never recreates
docker compose logs -f db
docker inspect --format='{{.State.Health.Status}}' "$(docker compose ps -q db)"

# MySQL shell inside the db container
docker compose exec db mariadb -u root -p iwmsdbGovernment
```

`up -d db` is deliberately used by CI instead of `--force-recreate`/`down`,
so an existing container and its volume are left untouched.

### Logs

```bash
docker compose logs -f backend                  # follow
docker compose logs --tail 100 backend          # last 100 lines
docker compose logs --since 24h backend | grep generate_daily_trips
journalctl -u iwms-government-backend -f        # systemd's view of the lifecycle
```

### Django commands (inside the running container)

```bash
docker compose exec backend python manage.py migrate --noinput
docker compose exec backend python manage.py collectstatic --noinput
docker compose exec backend python manage.py showmigrations --plan | grep '^\[ \]'
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py shell

# Backfill a missed nightly run (idempotent, safe to re-run)
docker compose exec backend python manage.py generate_daily_trips --date 2026-09-09
```

Add `-T` when scripting (no TTY) — that is what the workflow uses:

```bash
docker compose exec -T backend python manage.py migrate --noinput
```

> **Why migrations must run *inside* the container:** `**/migrations/*` is
> gitignored, so a CI checkout has an empty `app/migrations/` and `migrate`
> would die with `ValueError: Dependency on app with no migrations: app`.
> `docker-compose.yml` bind-mounts the server's real migration files
> (`./app/migrations:/app/app/migrations`), so running inside the container
> uses the true migration history.

### Shell inside a container

```bash
docker compose exec backend bash     # backend is Debian-based
docker compose exec db bash
docker compose run --rm backend bash # throwaway container, app not running
```

### Building

```bash
docker build -t ghcr.io/zigmasoftware/iwms-government-backend:latest .
docker compose build --no-cache backend   # ignore layer cache
docker compose up -d --build              # rebuild then recreate
```

This server **builds locally** — nothing is pushed to GHCR, so
`docker compose pull` fails. See
[09](09-docker-cutover-2026-09-08.md) §`pull` vs `build`.

### Cleanup

```bash
docker image prune -f        # dangling images only — safe, CI runs this
docker system df             # what is using disk
```

Avoid `docker system prune -a` here: it removes images still referenced by
stopped containers and forces a slow full rebuild.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `service "backend" is not running` during a deploy | The unit crash-looped on restart; the real error is earlier | `diff` installed unit vs `deploy/systemd/` (above), then `journalctl -u iwms-government-backend -n 50` |
| `no configuration file provided: not found` | A `-f docker-compose.production.yml` left over somewhere — that file was renamed | Drop the `-f` flag; the default `docker-compose.yml` is picked up automatically |
| `systemctl restart` succeeds but nothing works | `Type=simple` reports success on spawn, not on readiness | `sleep 5 && systemctl is-active iwms-government-backend` |
| `sudo: a password is required` in a CI step | Command string not in `deploy/sudoers/iwms-runner` (e.g. an extra flag like `--quiet`) | Use the exact allowed string, or add the new one to the sudoers file |
| A command works for you but fails in CI | You had a cached sudo timestamp; the runner is `iwmsuser` with a narrow allow-list | Re-test with `sudo -k` then `sudo -n ...` |
| `error: pathspec 'deploy/systemd/...' did not match any file(s)` | `deploy/systemd/` is gitignored — git has no copy | Expected. Use the file already on disk |
| Permission denied writing `static/` or `media/` | Docker created the dir as `root` via a bind mount | Re-run the `chgrp`/`chmod`/setgid block above |
| Deploy is green but the code is old | The deployment clone lagged `main` | The workflow's "Sync the deployment directory" step handles this; check it ran |

## Related docs

- [07-deployment-and-troubleshooting.md](07-deployment-and-troubleshooting.md) — general deployment + the main troubleshooting table
- [09-docker-cutover-2026-09-08.md](09-docker-cutover-2026-09-08.md) — full Docker basics; note some filenames there are now stale
- [10-local-docker-testing.md](10-local-docker-testing.md) — running the same stack locally
- [11-server-deploy-from-sathya.md](11-server-deploy-from-sathya.md) — branch → PR → `main` → what CI does
