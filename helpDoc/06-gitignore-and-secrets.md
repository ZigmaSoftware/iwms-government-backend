# 06 — .gitignore and Secrets

## The principle

Git history is permanent and shared. Anything committed once is on every
clone and every fork of the repo, forever, even after you delete the file in
a later commit. So the rule is simple:

> **Credentials never enter git. Not once, not "temporarily", not in a
> comment, not in a `.txt` file.**

## What is ignored, and why

### `.env` — machine-specific secrets

```gitignore
.env
.env.*
!.env.example
```

This holds the real database password, the SMTP account password, the
Firebase credentials path, and the API keys. It differs per machine anyway,
so tracking it would break your colleagues even if it were safe — which it
is not.

`.env.example` is meant to be the exception (`!.env.example`): it should
list every key from the table in
[02-database-and-env.md](02-database-and-env.md) with empty or safe
placeholder values. **This file does not exist yet in this repo** — creating
it is open follow-up work; see the checklist below.

### `app/migrations/` — generated per machine

```gitignore
**/migrations/*
!**/migrations/__init__.py
!app/migrations/0002_dailytripcollectionpoint_carried_to_assignment_and_more.py
```

Same deliberate team decision as the private backend, to avoid constant
migration-numbering conflicts — explained fully in
[02-database-and-env.md](02-database-and-env.md), including the one extra
exception this repo carves out and the real numbering collision already
sitting on disk because of it.

### Generated output — never commit

```gitignore
__pycache__/  *.py[cod]  *.pyo  *.pyd  *.pyc     # compiled Python
venv/ env/ .venv/ .uv-cache/                        # virtualenv, uv cache
media/ staticfiles/ static/                          # uploads and static output
*.log  db.sqlite3  *.sqlite3                          # logs and local databases
build/  dist/  *.egg-info/
```

`media/` is worth calling out: those are photos users uploaded on a
particular server. They are not source code, and committing them mixes one
deployment's data into everyone's clone.

### Editor and OS files

```gitignore
.vscode/  .idea/  .DS_Store  Thumbs.db
```

### Local AI prompts

```gitignore
/prompt.md
```

## Real leak found in this repo — read this

An audit of both this backend and its sibling frontend
(`iwms-government-frontend`) found that **`.env` had been committed
repeatedly**:

- `iwms-government-backend/.env` — committed **5 times**, containing
  `SECRET_KEY`, `DB_PASSWORD`, `EMAIL_HOST_PASSWORD`, `MY_API_KEY`,
  `ORS_API_KEY`, and the OTP/Firebase settings.
- `iwms-government-frontend/.env` — committed **37 times**.

The backend's `.gitignore` had actually had the right rules **written but
commented out**:

```gitignore
# === Environment files ===
# .env
# .env.*
```

That is a trap worth naming explicitly: a commented-out ignore rule looks
like it's handled at a glance, but does nothing — `.env` was tracked the
entire time. The frontend's `.gitignore` didn't mention `.env` at all.

### What has been fixed

Both `.gitignore` files now correctly ignore `.env`/`.env.*` (keeping a
`!.env.example` exception for when that template file is added), and both
tracked `.env` files have been removed from git's index with
`git rm --cached .env` — the files remain on disk, untouched, but will no
longer be included in future commits.

**This does not remove them from history.** Anyone with a clone, or with
access to the remote, can still read every old value by checking out an
earlier commit or running `git log -p -- .env`.

### What must still be done

Because those credentials are in the history, they should be treated as
compromised and rotated:

- [ ] MySQL password for the IWMS government database user
- [ ] `SECRET_KEY` (changing it invalidates every issued JWT — **and this
      backend issues both access and refresh tokens, so this logs everyone
      out and invalidates every outstanding refresh token at once**; do it
      at a quiet time)
- [ ] SMTP account password (`EMAIL_HOST_PASSWORD`)
- [ ] `MY_API_KEY` and `ORS_API_KEY`
- [ ] The Firebase service-account credentials, if `FIREBASE_CREDENTIALS_PATH`
      was ever pointed at a file whose contents also leaked
- [ ] Anything the frontend's committed `.env` exposed (check its own
      `VITE_*` keys — build-time env vars are visible to end users anyway,
      but any backend URL/key baked in there is worth reviewing)

Optionally, purge them from history with `git filter-repo` — but that
rewrites history, so every developer must re-clone. Agree it with the team
first. Rotating the credentials is the part that actually closes the hole;
history rewriting only reduces the exposure of the old values.

### Also still open: create `.env.example`

Since no `.env.example` exists, do this in the same sitting as rotating
secrets:

```bash
cp .env.example .env   # once you've created .env.example from the key
                        # table in 02-database-and-env.md, with placeholder
                        # values, and committed it
```

Every key in the table in [02](02-database-and-env.md) should appear in
`.env.example` with an empty or obviously-fake value — including the two
dead keys (`DB_ENGIBNE`, `EMAIL_APP_NAME`, `SERVER_PORT`) is optional, but
if you drop them, drop them from `.env` too rather than leaving silent
cruft.

## Habits that keep this from happening again

**Read `git status` before every commit.** Most leaks are one careless
`git add .`.

**Prefer explicit adds:**

```bash
git add app/ tests/        # not: git add .
```

**Check what you are about to commit:**

```bash
git diff --cached
```

**Check whether a file is ignored:**

```bash
git check-ignore -v .env
```

**Check nothing sensitive is tracked:**

```bash
git ls-files | grep -iE "\.env|secret|password|\.pem|\.key"
```

**If a `.gitignore` rule looks right, verify it's not commented out.** This
repo's own history is the counter-example — the rule existed, just disabled.

**If you do commit a secret:** say so immediately — the fix is rotating the
credential, and that only works if the team knows. Quietly deleting the file
in a follow-up commit does nothing; the value is still in history.

Next: [07-deployment-and-troubleshooting.md](07-deployment-and-troubleshooting.md).
