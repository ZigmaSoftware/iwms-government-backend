# CI/CD Flow (Backend)

The full path from a developer's laptop to the live production API, and the
self-hosted runner that makes it work. Read
[02-production-deploy.md](02-production-deploy.md) first for what the
workflow's steps actually do — this file is about the **branch flow** and the
**machine that executes it**.

## Branch flow

```
<developer> (sathya, sameer, dimple, gopi, lux, vinoth, ...)
        │  PR
        ▼
      dev
        │  PR
        ▼
      main  ──push──▶  GitHub Actions ──▶ self-hosted runner ──▶ Docker build
                                                                       │
                                                                       ▼
                                                         systemd restart on the
                                                         production server
```

- Each developer works on their own branch (named after themselves) and opens
  a PR into `dev`.
- `dev` accumulates changes from multiple developers before they go live.
- A PR from `dev` into `main` is what actually ships — **only `main` triggers
  a deploy.** Pushing directly to `dev`, to an individual developer branch, or
  to any branch other than `main` does nothing; the workflow does not even
  start.
- A manual re-deploy of the current `main` is possible from the Actions tab
  (`workflow_dispatch`) without a new push.

## The full mechanism, one diagram

```
push to main
     │
     ▼
GitHub Actions queues the "deploy" job
     │
     ▼
actions-runner-backend (installed ON the server, running as a
systemd service) polls GitHub outbound over HTTPS and picks up the job
     │
     ├─ authenticates using its own SAVED CREDENTIAL from registration
     │  (.runner / .credentials files — see "How the runner registers"
     │  below). This is NOT a Personal Access Token — no PAT exists
     │  anywhere in this pipeline.
     │
     ▼
actions/checkout@v4 checks out the new commit into the RUNNER'S OWN
workspace (actions-runner-backend/_work/...) — authenticated with
GitHub's auto-generated, run-scoped GITHUB_TOKEN, not a PAT either
     │
     ▼
docker build .        (runs locally, right there on the server,
                        tags the image :<sha> and :latest)
     │
     ▼
git fetch + checkout --force the SEPARATE persistent deployment clone
at /home/admin/localserver/iwmsGovernment/iwms-government-backend
to the same commit (this is NOT the runner's workspace above —
see "There are TWO checkouts" in 02-production-deploy.md)
     │
     ▼
sudo systemctl restart iwms-government-backend
     │
     ▼
systemd runs the .service file's ExecStart:
  docker compose -f docker-compose.prod.yml up --remove-orphans
     │
     ▼
docker compose sees :latest now points at the new image,
recreates the `backend` container from it
     │
     ▼
migrate / collectstatic / health-check run inside that new container
```

Two credentials are involved and **neither is a PAT**:
1. The runner's own long-lived credential (from one-time registration) —
   authenticates the runner itself to GitHub.
2. `GITHUB_TOKEN` — GitHub auto-generates a new one for every workflow run,
   scoped only to that run, used by `actions/checkout@v4` to clone the repo.
   You never create, store, or see this token; the runner receives it
   automatically as part of the job.

No secret named anything like `PAT`, `GH_TOKEN`, or similar is stored in
either repo's Actions secrets — see "Repo secrets and variables" below for
what actually *is* stored there (and confirmed unused).

## Why a self-hosted runner, not GitHub's cloud runners

GitHub's cloud runners cannot reach this server: of the ports forwarded from
the public IP (`115.245.93.26` → `192.168.1.128`), only `80`, `3000` and
`9001` are open — **port 22 (SSH) is not forwarded**, and other common SSH
ports were confirmed refused too. The "normal" GitHub Actions deploy pattern
— a GitHub-hosted runner reaches *into* your server (SSH, copy files, run
remote commands) — simply cannot work here, because nothing can connect
inbound.

A self-hosted runner flips the direction entirely, and that's the key thing
to understand about how this whole pipeline works:

1. A small runner program (`actions-runner-backend`) is installed **on this
   server itself**, running as a background service under systemd.
2. It continuously **polls GitHub outbound over HTTPS** — "any jobs queued
   for me?" — the same direction a browser making a request works. No
   inbound port, no firewall rule, no SSH key needed for this step.
3. When you push to `main`, GitHub marks a job ready. The runner picks it up
   on its next poll.
4. From there, **everything runs locally, in that runner's own process,
   because the runner already IS a process on this server.** `git
   checkout`, `docker build`, `docker compose`, `systemctl restart` are
   ordinary shell commands executing on this exact machine — not remote
   commands sent over a connection. There is no "reaching the server" step
   to speak of, because the work was never anywhere else.
5. The runner reports the result back to GitHub (again, outbound) — that's
   what populates the Actions tab's log.

This is also why `SERVER_HOST`/`SERVER_SSH_KEY`/`SERVER_USER` (see below)
are unused: those secrets exist to let something *external* log into the
server. Nothing external ever needs to, since the worker doing the deploy
is already inside.

A side effect: this also removes GHCR from the deploy path — the image is
built directly on the machine that runs it, so there is no push, pull, or
registry authentication step.

## Repo secrets and variables

GitHub → repo → **Settings → Secrets and variables → Actions** has two
separate tabs, and it's easy to conflate them:

**Secrets** (encrypted, never shown again once saved) — this repo currently
has `SERVER_HOST`, `SERVER_SSH_KEY`, `SERVER_USER`. **None of them are
referenced anywhere in `deploy.yml`.** They're leftovers from an earlier
design where a GitHub-hosted runner would SSH into the server to deploy —
the design this repo abandoned in favor of the self-hosted runner precisely
*because* port 22 isn't forwarded (see above). They're harmless sitting
there unused, but if you're looking for where SSH credentials are consumed
in this pipeline: they aren't. There's nothing to update here when the
server's IP or SSH key changes, because nothing reads them. Safe to delete;
also safe to leave in case a future workflow ever needs SSH again.

**Variables** (plain text, visible in the UI) — the frontend repo actually
uses these: `VITE_API_PROD`, `VITE_GPS_VEHICLE_API`,
`VITE_WEIGHBRIDGE_WASTE_API`, `VITE_WEIGHBRIDGE_WASTE_COLLECTION_KEY`,
`VITE_WEIGHBRIDGE_WASTE_COLLECTION_CORS_PROXY` — read as
`vars.VITE_API_PROD` etc. in `deploy.yml`, each with a hardcoded fallback
(`vars.VITE_API_PROD || 'http://115.245.93.26:9001/api/v1'`) so the build
still works even if no variable is set. These aren't secret on purpose —
anything baked into a frontend bundle is downloadable by any user, so
there's nothing to protect by encrypting them (full list and fallback
values: `../../iwms-government-frontend/helpDoc/04-cicd-flow.md`). **This
backend repo defines no repo variables** — it has no equivalent build-time
values to inject; its own config lives entirely in the server's `.env` file
instead (see [01-local-dev.md](01-local-dev.md)).

To change a variable's value without a code change: GitHub → this repo (or
the frontend repo) → **Settings → Secrets and variables → Actions →
Variables tab → New repository variable** (or edit an existing one) — takes
effect on the *next* push/re-run, it does not itself trigger a deploy.

## Where SSH actually fits (it doesn't, in the running pipeline)

Because the whole point of the self-hosted runner is to avoid needing SSH
into the server, **no step in either workflow opens an SSH connection**.
The closest thing to "logging into the server" that CI does is: the runner
process is *already running on the server*, so its `run:` steps
(`docker build`, `systemctl restart`, etc.) execute as local shell commands,
not remote ones — there's no connection to make.

SSH is still how a *human* gets onto this machine to install/manage the
runner itself, install a systemd unit, or debug something CI can't reach —
that's ordinary server access, unrelated to the deploy pipeline, and doesn't
use `SERVER_SSH_KEY` either (that secret isn't consumed by anything).

## What is installed on the server (backend runner)

| | Value |
|---|---|
| Runner directory | `/home/admin/localserver/iwmsGovernment/actions-runner-backend` |
| Runner name | `iwms-gov-backend` |
| Label | `iwms-government` (matches `runs-on: [self-hosted, iwms-government]` in `deploy.yml`) |
| systemd unit | `actions.runner.ZigmaSoftware-iwms-government-backend.iwms-gov-backend` |
| Runs as | `admin` (or `iwmsuser` — both are covered by the sudoers rule) |

**This backend has its own runner, entirely separate from the frontend's.**
Runners are registered per-repository, so the frontend repo has its own
runner process (`iwms-gov-frontend`) with its own directory and systemd unit
— see the frontend's `helpDoc/04-cicd-flow.md`. Both happen to run on the
same physical machine and share the same `iwms-government` label, but they
are two independent processes: a backend push never wakes the frontend
runner, and vice versa.

### How the runner registers and stays connected

"Connecting to the server" is the wrong mental model here — the runner
doesn't reach the server from outside, it's a program **physically
installed on** the server that reaches out to GitHub. Two separate steps:

**One-time registration** (already done — this is how it was originally set
up, not something that happens on every deploy):
1. GitHub → repo → **Settings → Actions → Runners → New self-hosted
   runner** mints a short-lived **registration token** (expires in about an
   hour, used exactly once).
2. On the server, `./config.sh --url <repo-url> --token <token> --name
   iwms-gov-backend --labels iwms-government` sends that token to GitHub to
   prove this machine may register.
3. GitHub responds by issuing a **long-lived credential**, which `config.sh`
   saves locally as `.runner` and `.credentials` files inside the runner's
   own directory. The one-hour registration token is now spent and
   irrelevant — this saved credential is what the runner actually uses from
   here on.
4. `sudo ./svc.sh install admin && sudo ./svc.sh start` wraps the runner as
   a systemd service so it starts on boot and stays supervised.

**Ongoing connection** (this is the part that runs 24/7): using that saved
credential, the runner process holds an outbound HTTPS long-poll to GitHub
— continuously asking "any jobs for me?" This is the same pattern a chat
app uses to receive messages without opening a port: purely outbound, no
listener on this server, nothing for a firewall to block. When a push to
`main` queues a job, the next poll picks it up.

## What the backend runner actually does, end to end

1. **GitHub queues the job** against any registered runner for this repo
   whose labels match `[self-hosted, iwms-government]` — here, that's always
   `iwms-gov-backend`.
2. **The runner polls it up outbound**, checks out the new commit into its
   own workspace (`actions-runner-backend/_work/...`), and starts the job.
3. **`docker build`** runs right there on the server, tagging the image with
   both the commit SHA and `:latest`.
4. **The persistent deployment clone** at
   `/home/admin/localserver/iwmsGovernment/iwms-government-backend` (a
   separate, permanent checkout — not the runner's own throwaway workspace)
   is fast-forwarded to the same commit.
5. **A smoke test** runs the new image against the production database before
   anything live is touched, so a broken image never reaches real traffic.
6. **systemd restarts the service**, which brings up `backend` via
   `docker-compose.prod.yml`.
7. **Migrations, static files, and health checks** run inside the now-running
   container.
8. The runner goes back to idle, polling for the next push to `main`.

Only one deploy can be in flight at a time (`concurrency: group:
deploy-backend`), so two rapid pushes never touch the same containers
simultaneously — the second waits for the first to finish rather than racing
it.

## Operating the runner

```bash
cd /home/admin/localserver/iwmsGovernment/actions-runner-backend
sudo ./svc.sh status
sudo ./svc.sh stop
sudo ./svc.sh start
```

Logs: GitHub → repo → **Actions** tab shows every run; the runner's own
process logs live under `_diag/` in its directory.

If a run is stuck **"Queued"** forever, the runner is offline or its label
doesn't match — check `svc.sh status`, and confirm the runner is still
registered under **Settings → Actions → Runners** in GitHub.

## Related docs

- [02-production-deploy.md](02-production-deploy.md) — what the workflow's steps do to the running service.
- [03-troubleshooting.md](03-troubleshooting.md) — sudoers/permission failures specific to the runner's restricted commands.
- `../../iwms-government-frontend/helpDoc/04-cicd-flow.md` — the frontend's own runner, same pattern, separate process.
