# 08 — Unit Testing Guide

## How testing is set up here

The suite uses **pytest** with **pytest-django**, configured in
`pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
DJANGO_SETTINGS_MODULE = "config.test_settings"
pythonpath = ["."]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = ["django_db: mark tests that need the Django test database"]
addopts = ["--tb=short", "--strict-markers", "-q"]
```

Those naming rules matter: a file called `continent_test.py`, or a class
called `ContinentTests`, is **silently not collected**. If your new test
"passes" suspiciously fast, check the name first. `--strict-markers` means a
typo'd marker (`@pytest.mark.djano_db`) fails the run instead of quietly
doing nothing — deliberate.

### Tests run on SQLite, not MySQL

`config/test_settings.py` imports everything from `config/settings.py` and
then replaces the database with **SQLite in-memory**. Two details worth
knowing before you touch this file:

1. **`SECRET_KEY` is defined *before* the wildcard `from .settings import
   *`.** This isn't stylistic — `settings_jwt.py` does a re-entrant read of
   `django.conf.settings.SECRET_KEY` during Django's `LazySettings` proxy
   load, and getting the ordering wrong reintroduces a circular-import
   failure. Leave it alone; the comment in the file explains it in detail.
2. **`MIGRATION_MODULES = {"app": None}`** disables migrations entirely
   during tests, so Django's test runner builds every table straight from
   the current models (`syncdb`-style) instead of replaying migration
   history. This sidesteps the `0002_*` numbering collision described in
   [02](02-database-and-env.md) entirely — tests never see it.

It also swaps `PASSWORD_HASHERS` to just `MD5PasswordHasher` for speed —
never rely on that for anything security-sensitive; it's test-only.

The trade-off of SQLite: anything MySQL-specific is not covered. Raw SQL,
MySQL-only functions and collation-dependent ordering can pass here and fail
in production. Keep queries in the ORM where you can.

## If you come from JUnit

| JUnit | pytest |
|---|---|
| `@Test` | any function named `test_*` |
| `class FooTest` | `class TestFoo` |
| `assertEquals(a, b)` | `assert a == b` |
| `@Before` | a fixture argument |
| `@BeforeAll` | a `scope="module"` fixture |
| `assertThrows(...)` | `with pytest.raises(...):` |

The big difference is **fixtures**. Instead of setup methods mutating shared
state, you declare what a test needs as a function argument, and pytest
builds it:

```python
def test_something(district, state):   # both come from tests/conftest.py
    ...
```

## Fixtures in `tests/conftest.py`

Available to every test without importing. Reflect this backend's actual
scoping model — a mix of a still-present company/project pair (see the note
below) and the geography hierarchy that drives real request scoping:

- `company(db)`, `project(db, company)` — still present even though the
  public-facing scoping model has moved to flat geography FKs (see
  [01-architecture-overview.md](01-architecture-overview.md)). Treat these
  as supporting internal/legacy models that still reference a company or
  project, not as the primary scoping mechanism to test against.
- `continent(db)`, `country(db, continent)`, `state(db, continent,
  country)`, `district(db, continent, country, state)`, `city(db,
  continent, country, state, district)`, `area_type(db, state, district,
  city)`, `zone(db, state, district, city)`, `corporation(db, state,
  district)`, `ward(db, state, district, corporation)` — the geography
  chain. Use these to build realistic `StaffDataScope` scenarios.
- `user_type(db)`, `superuser(db)` — auth/role basics. `superuser` bypasses
  geography scoping entirely (see 01), so use it deliberately, not as the
  default test user.
- `api_client()`, `auth_client(api_client, superuser)` — DRF test clients,
  the second pre-authenticated as a superuser.

`db` is pytest-django's own fixture: taking it (directly, or via another
fixture that takes it) gives the test a database and rolls back afterwards,
so tests never leak rows into each other.

## Writing a model test — worked example

Same shape as any Django model test in this codebase:

```python
"""Unit tests for District model — CRUD + constraints."""
import pytest
from app.models.masters.district import District


@pytest.mark.django_db
class TestDistrictCreate:
    def test_basic_create(self, state):
        d = District.objects.create(name="Example District", state=state)
        assert d.name == "Example District"

    def test_unique_id_prefix(self, state):
        d = District.objects.create(name="Another District", state=state)
        assert d.unique_id  # prefixed string id, not an integer

    def test_str(self, state):
        d = District.objects.create(name="Coastal District", state=state)
        assert str(d) == "Coastal District"


@pytest.mark.django_db
class TestDistrictDefaults:
    def test_is_active_default_true(self, state):
        d = District.objects.create(name="New District", state=state)
        assert d.is_active is True
```

Three things to copy from it:

1. **`@pytest.mark.django_db`** on any test that touches the database.
   Without it the test errors out rather than silently skipping.
2. **Group related assertions into `Test*` classes** — create, defaults,
   constraints, soft-delete, scoping. It makes failures easy to read.
3. **Cover the conventions, not just the happy path.** Every model here has
   a prefixed `unique_id` primary key, an `is_active` default, and an
   `is_deleted` soft-delete flag. Models with geography FKs should also be
   tested for what a `StaffDataScope`-restricted query does and doesn't
   return — that's where a scoping bug becomes a real data leak.

Mirror the app's layout when placing the file: a model at
`app/models/masters/leader_management/district_leader_login.py` gets a test
at `tests/masters/test_models/test_district_leader_login.py` (or wherever
the neighbouring tests for that folder already live — check `tests/` for
the closest existing match before inventing a new path).

## Running the suite

```bash
python -m pytest tests/ -q                       # everything
python -m pytest tests/masters/ -q               # one folder
python -m pytest tests/login/ -q                 # e.g. the login/captcha tests
python -m pytest tests/ -k "district" -q         # by name
python -m pytest tests/ -x                       # stop at first failure
python -m pytest tests/ -q --tb=long             # full tracebacks
```

## Coverage

Configured in `pyproject.toml` under `[tool.coverage.*]`, `source = ["app"]`,
excluding migrations, admin, the app config, tests, management commands and
signals.

```bash
# Terminal, with the uncovered line numbers
python -m pytest tests/ --cov=app --cov-report=term-missing -q

# Browsable HTML report -> htmlcov/index.html
python -m pytest tests/ --cov=app --cov-report=html -q && xdg-open htmlcov/index.html

# XML, for CI tools
python -m pytest tests/ --cov=app --cov-report=xml -q
```

All three outputs (`htmlcov/`, `coverage.xml`, `.coverage`) are git-ignored —
they are regenerated on every run, so never commit them.

## What is worth testing here

Highest value first:

1. **Model constraints** — uniqueness, defaults, soft-delete, the
   `unique_id` prefix.
2. **Serializer validation** — that bad input is rejected with a clear
   message, not a 500.
3. **Geography scoping** — that a staff member scoped to one district
   cannot read another district's rows, and that a staff member with no
   `StaffDataScope` grant gets an empty result rather than everything. This
   is the government backend's equivalent of the private backend's
   company/project leak risk, and it's the one where a bug means a real
   data leak.
4. **Login and JWT behavior** — the captcha gate, and that a refresh token
   actually issues a new access token via `login/refresh-token` without
   requiring a full re-login.
5. **Services** — trip generation, complaint ticket routing.

Back to [00-START-HERE.md](00-START-HERE.md).
