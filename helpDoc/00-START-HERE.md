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
   First-time server setup, `ALLOWED_HOSTS`/CORS, the shell scripts this repo
   actually ships (`manage.sh`, `scheduler.sh`, `server_uv_sync.sh`), and a
   troubleshooting table of real problems already hit.
8. **[08-unit-testing-guide.md](08-unit-testing-guide.md)** — How the test
   suite is wired (pytest + SQLite in-memory), the fixtures available in
   `conftest.py`, how to write a model test, and how to run coverage.

## The one-paragraph map of the whole project

```text
iwms-government-backend/
├── manage.py             <- the entry point for every django command
├── manage.sh             <- wrapper: uses .venv if present, else `uv run`
├── scheduler.sh           <- the nightly trip-generation cron entry point
├── server_uv_sync.sh      <- `uv sync --locked` wrapper for deploys
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
