# IWMS Government Backend — Help Docs (Start Here)

This `helpDoc/` folder explains the entire `iwms-government-backend` project
from scratch, assuming you know nothing about it yet — not the architecture,
not Django, not this team's specific workflow. Read the files in order the
first time; after that, use them as reference.

If you only remember one thing from this whole folder, remember this:

> **This is ONE Django project with ONE database and ONE app (`app/`). It is
> not microservices. What makes it look big is that a single app holds every
> module — masters, staff, complaints, leader portals, reports — each exposed
> under its own URL group. Database tables are NOT created by pulling code;
> they appear only when someone runs `migrate` on that machine, and sample
> data appears only when someone runs `seed`.**

This backend is the sibling of `iwms-backend` ("private") — same Django/DRF
stack, same `GroupedRouter` URL convention, same not-tracking-migrations
strategy — but it serves a different audience: **government/civic bodies**
(state → district → local body → ward), not multi-tenant companies. Where
they diverge is called out explicitly throughout this folder rather than
assumed.

## Reading order

1. **[01-architecture-overview.md](01-architecture-overview.md)** — What the
   project actually is: one Django project, one app, many URL groups. How a
   request travels from the browser to a database row and back.
2. **[02-database-and-env.md](02-database-and-env.md)** — Where the
   database host/password come from, the `.env` file, how to create the
   MySQL database, and how migrations really work here.
3. **[03-app-structure.md](03-app-structure.md)** — A tour of `app/`:
   models, serializers, viewsets, permissions, middleware, services, and how
   the custom router turns a viewset into a URL.
4. **[04-commands-reference.md](04-commands-reference.md)** — Every command
   you will actually type: setup, run, migrate, seed (all groups listed),
   backfill commands, the nightly scheduler.
5. **[05-team-workflow.md](05-team-workflow.md)** — The day-to-day workflow:
   a developer builds a feature locally, pushes code, and what each other
   developer must run to get the new tables on their own machine.
6. **[06-gitignore-and-secrets.md](06-gitignore-and-secrets.md)** — What is
   and isn't tracked in git, and why (passwords, migration files, caches,
   per-machine scripts) — including a real leak found and fixed in this
   repo, and what to still do about it.
7. **[07-deployment-and-troubleshooting.md](07-deployment-and-troubleshooting.md)** —
   Docker-based server deployment (see also [DEPLOYMENT.md](../DEPLOYMENT.md)
   at the repo root), `ALLOWED_HOSTS`/CORS, the shell scripts this repo
   actually ships (`manage.sh`, `server_uv_sync.sh` — both local-dev only
   now), the nightly trip scheduler (runs in-process, no cron involved),
   and a troubleshooting table of real problems already hit.
8. **[08-unit-testing-guide.md](08-unit-testing-guide.md)** — How the test
   suite is wired (pytest + SQLite in-memory), the fixtures available in
   `conftest.py`, how to write a model test, and how to run coverage.
9. **[09-docker-cutover-2026-09-08.md](09-docker-cutover-2026-09-08.md)** —
   What actually happened when this server moved from `.venv`+`runserver` to
   Docker on 2026-09-08: why the compose file (at the time named
   `docker-compose.production.yml`) used `network_mode: host` (and therefore
   had no `ports:`), why `SECRET_KEY` must keep its `$$` escaping, every
   command the cutover used, and the outstanding items — including
   `DEBUG=True` still being live in production. Ends with a **Docker basics**
   section — start/stop/restart, kill/recreate, logs, shells, images, health
   checks — which the frontend repo mirrors at
   `../../iwms-government-frontend/helpDoc/02-docker-basics.md`. Some
   filenames/commands here are now stale — see 10 below for what changed.
10. **[10-local-docker-testing.md](10-local-docker-testing.md)** — Run all
    three pieces (frontend, backend, **and** database) as three separate
    local containers. Covers the renamed `docker-compose.yml` (was
    `docker-compose.production.yml`), the new `db` service
    (`mariadb:11.8`), every command to bring it up/verify it/tear it down,
    and how to prove to yourself locally that `docker compose up -d db`
    never wipes existing data before trusting that same command in
    production.
11. **[11-server-deploy-from-sathya.md](11-server-deploy-from-sathya.md)** —
    The actual process to get code from a local branch (e.g. `sathya`) live
    on the production server: push → PR → merge to `main` → what the
    self-hosted runner does automatically, what stays manual (migrations,
    and the one-time data migration into the new `db` container), and how
    to confirm a deploy actually worked.
12. **[12-permissions-and-docker-commands.md](12-permissions-and-docker-commands.md)** —
    The two Linux accounts on the server (`admin`, who you log in as, and
    `iwmsuser`, who the Actions runner runs as), who owns which directories
    and how to repair them, why a command that works when you type it can
    still fail in CI, and the fact that `deploy/systemd/` is gitignored so
    the installed unit can silently go stale — the cause of the 2026-09-09
    deploy failure, walked through end to end. Ends with a **Docker command
    reference** using the current `docker-compose.yml` name (no `-f` flag).

## The one-paragraph map of the whole project

```text
iwms-government-backend/
├── manage.py             <- the entry point for every django command
├── manage.sh             <- local-dev wrapper: uses .venv if present, else `uv run`
├── server_uv_sync.sh      <- local-dev `uv sync --locked` wrapper
├── Dockerfile             <- production image: gunicorn (no cron — the
│                              nightly scheduler runs in-process, see 07)
├── docker-compose.yml     <- runs backend + db containers (renamed from
│                              docker-compose.production.yml; see 10 and 11)
├── deploy/                <- systemd unit template (gitignored)
├── config/                <- project settings (NOT a Django app)
│   ├── settings.py           <- database, apps, CORS, email, OTP, Firebase
│   ├── settings_jwt.py       <- token lifetime and signing (issues BOTH
│   │                            access AND refresh tokens — see 01)
│   ├── test_settings.py      <- same, but SQLite in-memory for tests
│   └── urls.py                <- top-level routes + Swagger UI
├── app/                  <- THE app — all business code lives here
│   ├── models/               <- database tables, grouped by domain
│   ├── serializers/          <- JSON in/out validation
│   ├── viewsets/             <- the API endpoints
│   ├── urls/                 <- custom router that builds /api/v1/<group>/...
│   ├── permissions/          <- who may call what
│   ├── middleware/           <- runs on every request
│   ├── services/             <- business logic too big for a viewset
│   ├── utils/hierarchy.py    <- the geography scoping engine — see 01
│   ├── management/commands   <- `seed`, backfills, `generate_daily_trips`
│   └── migrations/           <- generated per machine, NOT in git
├── tests/                <- pytest suite, mirrors the app structure
├── media/                <- user uploads (not in git)
├── .env                  <- this machine's own settings (NOT in git)
└── .env.example          <- does not exist yet — see 02 and 06
```

Everything the API serves is reachable under `/api/v1/`. Interactive API
docs are at `/api/v1/swagger/` once the server is running.

## Who is this for?

Anyone who needs to work on, deploy, or simply understand this backend —
including someone who has never opened this repo before and has no Django
background. Every file tries to explain *why* something is set up the way it
is, not just *what* the command is.
