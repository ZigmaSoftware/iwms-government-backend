# IWMS Government Backend — Start Here

Django + Django REST Framework API for government/civic waste management
(state → district → local body → ward). It is the sibling of the private
`iwms-backend`, same stack and URL-routing conventions, but scoped to
government hierarchy instead of multi-tenant companies.

> **If you remember one thing:** this is ONE Django project with ONE app
> (`app/`) — not microservices. Masters, staff, complaints, leader portals
> and reports are all modules inside that single app, each exposed under its
> own URL group. And `app/migrations/` is **gitignored** — pulling code never
> gives you the database schema. You must run `migrate` yourself on every
> machine (see [01-local-dev.md](01-local-dev.md)).

## The project, in one paragraph

```text
iwms-government-backend/
├── manage.py, manage.sh          <- entry point / local-dev wrapper
├── Dockerfile                    <- production image (gunicorn)
├── docker-compose.yml            <- LOCAL dev (backend + db containers)
├── docker-compose.prod.yml       <- PRODUCTION (backend only, external DB)
├── config/                       <- settings, urls, JWT config (not an app)
├── app/                          <- the app — all business code
│   ├── models/, serializers/, viewsets/, urls/   <- one module per domain
│   ├── permissions/, middleware/, services/, utils/
│   └── migrations/                <- generated per machine, NOT in git
├── deploy/                       <- systemd units, sudoers, Apache config
└── .env                          <- this machine's own settings, NOT in git
```

Everything is served under `/api/v1/`; interactive docs at `/api/v1/swagger/`.

## Where to go next

- **[01-local-dev.md](01-local-dev.md)** — run this repo on your own machine.
- **[02-production-deploy.md](02-production-deploy.md)** — what happens on
  push to `main`, and how to do it by hand if you ever need to.
- **[03-troubleshooting.md](03-troubleshooting.md)** — symptom → cause → fix.
- **[04-cicd-flow.md](04-cicd-flow.md)** — the branch flow (developer → `dev`
  → `main`) and the self-hosted runner that turns a push into a deploy.
