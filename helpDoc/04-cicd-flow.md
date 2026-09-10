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

## Why a self-hosted runner, not GitHub's cloud runners

GitHub's cloud runners cannot reach this server: of the ports forwarded from
the public IP (`115.245.93.26` → `192.168.1.128`), only `80`, `3000` and
`9001` are open — **port 22 (SSH) is not forwarded**, and other common SSH
ports were confirmed refused too. A self-hosted runner sidesteps this
entirely by **polling GitHub outbound over HTTPS** — nothing needs to be
forwarded inbound, and no SSH key is involved.

This also removes GHCR from the deploy path: the image is built directly on
the machine that runs it, so there is no push, pull, or registry
authentication step.

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
