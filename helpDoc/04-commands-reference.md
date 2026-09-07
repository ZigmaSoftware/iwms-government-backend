# 04 — Commands Reference

Everything you will actually type, in the order you need it. Run all of these
from the repo root (the folder holding `manage.py`), with the virtualenv
active — or use `./manage.sh <command>`, which finds `.venv` for you and
falls back to `uv run` if it isn't there yet.

## Environment setup

This project uses **[uv](https://docs.astral.sh/uv/)** to manage the
virtualenv and dependencies. `pyproject.toml` and `uv.lock` are the source of
truth; `requirements.txt` is kept alongside for tools that need it — but note
`requirements.txt` currently includes `firebase-admin` while
`pyproject.toml`'s dependency list does not, so a plain `uv sync` may not
install it. If push notifications stop working, check this first.

```bash
uv venv                      # create .venv/
source .venv/bin/activate    # Linux/macOS
uv sync                      # install everything from uv.lock
```

Adding a dependency:

```bash
uv add <package>             # updates pyproject.toml AND uv.lock — commit both
```

If you are not using uv:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires **Python 3.13+** (`pyproject.toml`).

Then create your `.env` — see [02-database-and-env.md](02-database-and-env.md).
No `.env.example` exists yet in this repo; ask a teammate for a working
`.env` or rebuild one from the key table in 02 until one is added.

## Running the server

```bash
python3 manage.py runserver                  # http://127.0.0.1:8000
python3 manage.py runserver 0.0.0.0:8000     # reachable from other machines
./manage.sh runserver                        # same, via the wrapper script
```

If you bind to a LAN address, that address must be in `ALLOWED_HOSTS` in
`config/settings.py`, and the frontend's origin must match one of the
`CORS_ALLOWED_ORIGIN_REGEXES`. See
[07-deployment-and-troubleshooting.md](07-deployment-and-troubleshooting.md).

Once it is up:

- `http://localhost:8000/api/v1/` — browsable index of every URL group
- `http://localhost:8000/api/v1/swagger/` — full API docs
- `http://localhost:8000/admin/` — Django admin

## Migrations

Remember: migration files are not in git, so you generate them yourself
(see [02](02-database-and-env.md), including the real `0002`-numbering
collision already sitting in this repo).

```bash
python3 manage.py makemigrations app
python3 manage.py migrate
python3 manage.py showmigrations      # what has and hasn't been applied
```

## Seeding sample data

`python3 manage.py seed` fills an empty database with a working dataset.
Without it a fresh database has no rows and the frontend has nothing to
show.

```bash
python3 manage.py seed                     # everything, in dependency order
python3 manage.py seed --group masters     # just one group
```

**Seeding is blocked outside local development** — `Command.handle()`
refuses to run unless `settings.ENVIRONMENT != "production"` **and**
`settings.DEBUG` is `True`. Both conditions must hold; you cannot seed a
production-configured environment even by accident.

**Order matters.** `seed` with no arguments runs `ORDERED_GROUPS` in this
sequence, because each depends on the ones before it:

```text
superadmin → common-masters → masters → waste-types → role-assigns
→ user-creations → transport-masters → schedule-setup
→ schedule-operations → screen-managements → collections
→ customer-masters → complaint-ticket → reports → driver-demo
```

(`audits` exists as a group but is currently commented out of the ordered
run — seed it explicitly with `--group audits` if you need it.)

The `--group all` composite list is **hand-curated, not just the ordered
groups flattened** — for example `CustomerCreation` must seed before
schedule operations (household trip assignments expand stops by querying
customers), but waste collections must seed *after* schedule operations
(they need those assignments to already exist). If you add a new seeder,
check where it actually needs to sit in this dependency chain, not just
which named group it logically belongs to.

### All `--group` values

**Main groups** (the ones in the ordered run above):

| Group | Seeds |
|---|---|
| `superadmin` | Company, project, super-admin user |
| `common-masters` | Continents, countries, states |
| `masters` | Districts, cities, zones, wards, panchayats, etc. |
| `waste-types` | Properties, sub-properties, waste types (merged from legacy `assets`) |
| `role-assigns` | User types, staff/contractor user types |
| `user-creations` | Staff office/personal records, auth users |
| `transport-masters` | Vehicle types, vehicles, fuel |
| `schedule-setup` | Collection points, bins, staff templates, alternative staff templates, trip plans |
| `schedule-operations` | Daily trip assignments/collection points/household collections/logs, bin collection events, vehicle breakdowns |
| `screen-managements` | Screen permissions |
| `collections` | Panchayat-, ward- and zone-wise collections |
| `customer-masters` | Customers, feedback, charge rules |
| `complaint-ticket` | Tickets, categories, teams, SLA and routing rules |
| `reports` | Monthly waste comparison |
| `driver-demo` | A driver login wired to a today trip (bin + household) |

**Single-seeder shortcuts:**

`scheduler-demo` · `bin-collection-events` · `waste-collections` ·
`retrip-demo` · `vehicle-breakdowns` · `blue-planet` · `driver-households`

**Legacy aliases** — kept working so old notes and scripts don't break:

`assets` → `waste-types` · `customers` → `customer-masters` ·
`user-creation` → `user-creations` · `staff` → `user-creations` ·
`vehicles` → `transport-masters` · `platform` → `superadmin` ·
`schedule-masters` → `schedule-setup` + `schedule-operations` (deliberately
excluded from `--group all` so it doesn't double-seed)

A wrong `--group` name is not silently ignored — the command prints the
valid list and stops.

## Backfill and one-off commands

```bash
python3 manage.py backfill_daily_trip_logs
python3 manage.py detect_sla_breaches        # complaint SLA breach detection
python3 manage.py generate_daily_trips       # create today's trips from plans
```

`generate_daily_trips` is the one that matters day-to-day — it is what the
nightly scheduler (`scheduler.sh`, see
[07-deployment-and-troubleshooting.md](07-deployment-and-troubleshooting.md))
actually runs via cron.

## Clearing Python caches

```bash
# Linux / macOS
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} +

# Windows PowerShell
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

## The one-liner: full local rebuild

```bash
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} + \
  && python3 manage.py makemigrations app \
  && python3 manage.py migrate \
  && python3 manage.py seed \
  && python3 manage.py runserver 0.0.0.0:8000
```

This assumes the database itself already exists. To drop and recreate it
first, see "Starting over locally" in
[02-database-and-env.md](02-database-and-env.md).

## Users and static files

```bash
python3 manage.py createsuperuser     # a login for /admin/
python3 manage.py collectstatic       # gather static files into staticfiles/
python3 manage.py check               # config sanity check, no DB needed
python3 manage.py shell               # interactive Django shell
```

## Tests and coverage

Full detail in [08-unit-testing-guide.md](08-unit-testing-guide.md). The
short version:

```bash
python -m pytest tests/ -q
python -m pytest tests/ --cov=app --cov-report=term-missing -q
python -m pytest tests/ --cov=app --cov-report=html -q && xdg-open htmlcov/index.html
```

Next: [05-team-workflow.md](05-team-workflow.md).
