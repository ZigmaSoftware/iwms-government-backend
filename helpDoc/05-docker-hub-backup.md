# Manual Docker Hub Backup (personal, not part of CI/CD)

> **This is NOT part of the real deploy pipeline.** Production never pushes to
> or pulls from any registry — see
> [04-cicd-flow.md](04-cicd-flow.md#why-a-self-hosted-runner-not-githubs-cloud-runners):
> the self-hosted runner builds each image directly on the server it runs on,
> so GHCR/Docker Hub are never part of that path. The steps below are a
> **manual, personal workflow** for pushing copies of the three project images
> to a Docker Hub account (`sk028` in the examples) — useful for backup,
> sharing an image outside this server, or working from a different machine.
> Running these commands changes nothing about how the actual server deploys.

## Prerequisites

```bash
docker login -u <your-dockerhub-username>
# password prompt: paste a Personal Access Token (PAT), not your account
# password — Docker Hub requires a PAT for CLI login.
docker info | grep -i username     # confirms who you're pushing as
```

Create/rotate a PAT at **https://app.docker.com/accounts/sk028/settings/personal-access-tokens** →
*Generate new token*. Give it an expiration and only **Read & Write** scope if
you intend to push. Docker Hub shows the token once — copy it immediately, it
can't be viewed again. Never paste a PAT or the contents of
`~/.docker/config.json` into a chat/doc/ticket — the `auth` field there is
just base64 of `username:token`, trivially reversible, so pasting it is the
same as pasting the raw token.

## 1. Backend image

```bash
cd iwms-government-backend
docker build -t <username>/iwms-government-backend:latest .
docker push <username>/iwms-government-backend:latest
```

Safe to push as-is: `.dockerignore` excludes `.env`, so no secrets are baked
into this image (`.env` is only ever read at container **runtime** via
`env_file:`, never copied into the build context).

## 2. Frontend image

The frontend bakes `VITE_*` values into the JS bundle at **build time** (see
[01-local-dev.md](01-local-dev.md) in the frontend repo), so they must be
passed as `--build-arg`, pulled from your local `.env`:

```bash
cd iwms-government-frontend
docker build \
  --build-arg VITE_ENV=prod \
  --build-arg VITE_API_PROD="$(grep ^VITE_API_PROD= .env | cut -d= -f2-)" \
  --build-arg VITE_GPS_VEHICLE_API="$(grep ^VITE_GPS_VEHICLE_API= .env | cut -d= -f2-)" \
  --build-arg VITE_WEIGHBRIDGE_WASTE_API="$(grep ^VITE_WEIGHBRIDGE_WASTE_API= .env | cut -d= -f2-)" \
  --build-arg VITE_WEIGHBRIDGE_WASTE_COLLECTION_KEY="$(grep ^VITE_WEIGHBRIDGE_WASTE_COLLECTION_KEY= .env | cut -d= -f2-)" \
  --build-arg VITE_WEIGHBRIDGE_WASTE_COLLECTION_CORS_PROXY="$(grep ^VITE_WEIGHBRIDGE_WASTE_COLLECTION_CORS_PROXY= .env | cut -d= -f2-)" \
  -t <username>/iwms-government-frontend:latest .
docker push <username>/iwms-government-frontend:latest
```

Nothing in this bundle is secret by design (it's downloadable by any site
visitor once deployed anyway) — pushing it publicly reveals nothing that
isn't already exposed by the live site.

## 3. Database image (re-tagged upstream MariaDB)

There's no custom `db` image in this project — `docker-compose.yml` uses
stock `mariadb:11.8` directly. "Pushing" it just re-tags the upstream image
under your own namespace; it adds no customization of its own:

```bash
docker pull mariadb:11.8
docker tag mariadb:11.8 <username>/iwms-government-db:11.8
docker push <username>/iwms-government-db:11.8
```

## Verify

```bash
docker images | grep <username>
```

Or check `https://hub.docker.com/u/<username>` in a browser.

## Related docs

- [04-cicd-flow.md](04-cicd-flow.md) — the actual, automated deploy path (no
  registry involved at all).
- `../../iwms-government-frontend/helpDoc/05-docker-hub-backup.md` — the
  frontend's own version of this doc, with its `VITE_*` build-arg gotchas.
