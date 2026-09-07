# 02 — Database and Environment

## The `.env` file — the one place settings live

`config/settings.py` calls `os.getenv(...)` for every value that differs
between machines: the database password, the email account, the API keys,
the Django secret key, the OTP configuration, the Firebase credentials path.

- **`.env` is required.** Without it, Django falls back to hard-coded
  defaults that will not match your machine.
- **`.env` must never be committed.** It should be in `.gitignore`. It
  previously WAS committed by mistake in this repo — see
  [06-gitignore-and-secrets.md](06-gitignore-and-secrets.md) for what
  happened and what still needs doing about it.
- **No `.env.example` exists yet in this repo**, even though `.gitignore`
  has a `!.env.example` exception ready for one. Creating it is the single
  highest-value follow-up from this documentation pass — see the checklist
  in [06](06-gitignore-and-secrets.md).

First thing on a fresh clone, once `.env.example` exists:

```bash
cp .env.example .env
# then open .env and fill in the real values
```

Until then, ask a teammate for a working `.env` or rebuild one from the key
table below.

### What each key does

| Key | Default if unset | Meaning |
|---|---|---|
| `SECRET_KEY` | *(required)* | Django's signing key. Also signs JWTs (`settings_jwt.py`). **Changing it logs everyone out.** |
| `DJANGO_ENV` | `development` | `development` → `DEBUG=True`. Anything else (`production`) → `DEBUG=False`. |
| `DB_NAME` | `iwmsdbGovernment` | Database name. |
| `DB_USER` | `root` | MySQL user. |
| `DB_PASSWORD` | `admin@123` (dev default only) | MySQL password. |
| `DB_HOST` | `localhost` | |
| `DB_PORT` | `3306` | |
| `MY_API_KEY` | `abc123` | Shared key checked by some internal endpoints. |
| `ORS_API_KEY` | *(empty)* | OpenRouteService — route optimisation. |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `DEFAULT_FROM_EMAIL` | Gmail SMTP defaults | SMTP account used to send OTP and password-reset mail. |
| `FIREBASE_CREDENTIALS_PATH` | *(empty)* | Path to a Firebase service-account JSON file, not committed to the repo. Push notifications (`app/services/push_notification_service.py`) are a safe no-op until this is set — leaving it empty does not crash anything. |
| `OTP_EXPIRY_MINUTES` | `5` | |
| `OTP_MAX_ATTEMPTS` | `3` | |
| `OTP_RESEND_COOLDOWN_MINUTES` | `2` | |
| `OTP_MAX_REQUESTS_PER_WINDOW` | `3` | |
| `OTP_RATE_WINDOW_MINUTES` | `10` | |
| `TRIP_ATTENDANCE_COOLDOWN_MINUTES` | `1` | Minimum gap between two attendance punches on one trip. |
| `ENABLE_AUTH_USER_SEEDING` | `true` | Set `false` to stop the seeder creating Django auth users. |

> **Note:** generate a fresh `SECRET_KEY` with
> `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.

### Two dead keys — don't waste time chasing them

- **`DB_ENGIBNE`** — this exact misspelling exists in the `.env` file, but
  `settings.py` reads the correctly-spelled `DB_ENGINE`. The typo means
  whatever you put in `DB_ENGIBNE` is **silently ignored** — the engine
  always falls back to the hard-coded default
  `django.db.backends.mysql`. If you ever need to actually change the DB
  engine, edit `config/settings.py` directly, not `.env` — or fix the typo
  in both places at once.
- **`EMAIL_APP_NAME`** and **`SERVER_PORT`** exist as keys in `.env` but are
  never read by any Python or shell file in this repo. Leftover cruft — safe
  to ignore, and worth dropping if you're cleaning up `.env.example`.

## Setting up MySQL / MariaDB

The project talks to MySQL through **PyMySQL** (a pure-Python driver, so you
do **not** need to compile `mysqlclient`).

```bash
# 1. Install the server (Debian/Ubuntu)
sudo apt install mariadb-server

# 2. Create the database and a user
sudo mysql -u root -p
```
```sql
CREATE DATABASE iwmsdbGovernment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'iwms'@'localhost' IDENTIFIED BY 'your-password-here';
GRANT ALL PRIVILEGES ON iwmsdbGovernment.* TO 'iwms'@'localhost';
FLUSH PRIVILEGES;
```

Then put that name/user/password into your `.env`.

Use `utf8mb4` — district, ward and citizen names include regional-language
text, and the older `utf8` collation cannot store all of it.

## Migrations — the part that surprises people

Look at `.gitignore`:

```gitignore
**/migrations/*
!**/migrations/__init__.py
!app/migrations/0002_dailytripcollectionpoint_carried_to_assignment_and_more.py
```

**Migration files are deliberately NOT tracked in git**, same strategy as
the private backend — with one extra, unusual exception.

### Why (and the live example of the risk, sitting in this repo right now)

The trade-off of not tracking migrations is that the schema is not
reproducible from git; every machine generates its own migration files from
the current models. This repo currently has a concrete example of what goes
wrong when that drifts: there are **two different `0002_...` files** on disk
— `0002_dailytripcollectionpoint_carried_to_assignment_and_more.py` (the one
git-tracked via the exception above) and
`0002_staffnotification_vehiclebreakdownphoto_and_more.py` (untracked,
local-only). There is also a separate `0005_add_carried_to_assignment.py`
that performs the **same two `AddField` operations** as the tracked `0002`
file. This is exactly the kind of numbering collision the "migrations
aren't in git" strategy risks — two developers' locally-generated migration
graphs diverged. The exact reason one specific `0002` file was carved out
and committed isn't recorded in its commit message; treat it as a "this file
matters, don't regenerate over it casually" marker rather than a mystery to
solve, and if your own `makemigrations` produces a conflicting `0002`, ask
before force-renumbering.

### What that means for you, every single time you pull

```bash
python3 manage.py makemigrations app
python3 manage.py migrate
```

Your machine generates its own migration files from the current models, then
applies them. Two developers can end up with differently-numbered migration
files that produce the same schema — usually harmless, but see above for
what happens when it isn't.

### The honest warning

This works while the project is young and everyone can afford to rebuild
their local database. It does **not** give you safe production schema
changes: a generated migration knows nothing about rows already on a live
database. If this system goes to production with data that must survive,
the first thing to change is to start tracking `app/migrations/` in git.
Raise it with the team rather than deciding alone.

### Starting over locally

```bash
mysql -u root -p -e "DROP DATABASE iwmsdbGovernment; CREATE DATABASE iwmsdbGovernment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} +
python3 manage.py makemigrations app
python3 manage.py migrate
python3 manage.py seed
```

Never do this on a server that holds real data.

## Browsing the data

- **phpMyAdmin** or any MySQL client, pointed at `DB_NAME`.
- **Django admin** at `http://localhost:8000/admin/` — needs a superuser
  (`python3 manage.py createsuperuser`, or one created by the seeder).
- **Swagger** at `http://localhost:8000/api/v1/swagger/` to poke the API
  itself rather than the tables.

Next: [03-app-structure.md](03-app-structure.md).
