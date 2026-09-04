# 01 — Architecture Overview

## What this project is

IWMS = **Integrated Waste Management System**. This repo is the government
backend: a single **Django 5.2 + Django REST Framework** project that serves
a JSON API to the government React frontend (`iwms-government-frontend`),
the state/district/local-body leader portals, and citizen-facing public
grievance endpoints.

Two things people usually get wrong on day one:

1. **It is not microservices.** There is one Django project, one database,
   one app. There are no per-service ports or per-service databases here.
2. **`app/` is the only Django app.** Everything — masters, staff, leader
   logins, schedules, complaints, reports — is a folder *inside* `app/`, not
   a separate installed app.

```text
                       ┌──────────────────────────────┐
   Browser / mobile ──▶ │ iwms-government-frontend (React) │
                       └───────────────┬──────────────┘
                                       │ HTTPS, JSON, Bearer token
                                       ▼
                       ┌──────────────────────────────┐
                       │  Django  (this repo)          │  runserver :8000
                       │  /api/v1/...                   │  or gunicorn
                       └───────────────┬──────────────┘
                                       │ SQL
                                       ▼
                       ┌──────────────────────────────┐
                       │  MySQL / MariaDB               │  one database
                       └──────────────────────────────┘
```

## How one request travels

Take `GET /api/v1/masters/districts/`.

1. **`config/urls.py`** is the front door. It sends anything starting with
   `api/v1/` into `app/urls/base_urls.py`.
2. **`app/urls/base_urls.py`** builds the routes with a custom
   `GroupedRouter.register_group()` (in `app/urls/custom_router.py`) — same
   pattern as the private backend. A line like:

   ```python
   router.register_group("masters", "districts", DistrictViewSet)
   ```

   produces the URL `/api/v1/masters/districts/`. The first argument is the
   **group**, the second is the **resource**.
3. **Middleware** runs before the view (see `config/settings.py`):
   - `ModulePermissionMiddleware` — checks the logged-in user is allowed to
     touch this module at all.
   - `RequestMetaMiddleware` — stashes the current user/request so models
     can record who created or changed a row.
4. **Authentication** — a custom class,
   `app.authentication.jwt.JWTUserAuthentication` (`config/settings.py`
   `DEFAULT_AUTHENTICATION_CLASSES`). The frontend sends
   `Authorization: Bearer <token>`. Tokens are HS256, signed with
   `SECRET_KEY`.
5. **The viewset** (`app/viewsets/...`) handles the request, applies
   permissions, and asks the serializer for data. Most list endpoints also
   run their queryset through the geography-scoping helpers in
   `app/utils/hierarchy.py` (see "Scoping" below).
6. **The serializer** converts model rows to JSON on the way out, and
   validates JSON on the way in.
7. **The model** is the actual database table.
8. JSON comes back up the same chain.

## Two access tokens, not one — a real difference from the private backend

`config/settings_jwt.py` issues **both** an access token (5 hour lifetime)
**and** a refresh token (7 day lifetime):

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    ...
}
```

`app/viewsets/login/login_viewset.py` mints both
(`AccessToken.for_user(user)` and `RefreshToken.for_user(user)`), and there
is a dedicated `login/refresh-token` endpoint
(`app/viewsets/login/refresh_token_viewset.py`) to trade a refresh token for
a new access token without forcing a full re-login. **Refresh tokens are not
rotated or blacklisted on use** — a leaked refresh token stays valid for its
full 7-day life. Keep that in mind before treating it as a safe-by-default
long-lived credential.

`USER_ID_FIELD` is deliberately `"pk"` rather than a specific model's ID
field, because this system mints JWTs for more than one user-like model
(staff records and platform/company users have different primary keys, but
`pk` always resolves correctly for whichever one signed in).

## The URL groups

Every endpoint lives under one of these groups — the fastest map of what the
system does. This list is fuller than the private backend's because the
government side layers portal-specific and citizen-facing groups on top of
the same masters/schedule/complaint machinery:

| Group | What it holds |
|---|---|
| `common-masters` | Continents, countries, states |
| `masters` | Districts, panchayats, panchayat/district/state leader logins, area types, hierarchy, departments, designations, corporations, municipalities, town panchayats, panchayat unions, wards |
| `waste-types` | Properties, sub-properties, waste types, bins (absorbed the legacy `assets` group) |
| `screen-managements` | Screen/column/dashboard-widget permissions |
| `role-assigns` | User types, staff/contractor/**government** user types |
| `user-creations` | Staff records, staff access configuration/dashboard, unassigned staff pool |
| `login` | Login, **captcha**, my-permissions, refresh-token |
| `customer-masters` | Customers, feedback, user charge rules |
| `schedule-operations` | Waste collections, daily trip assignments/logs/collection points, bin collection events, vehicle breakdowns, retrip requests, staff notifications |
| `complaint-ticket` | Tickets, categories, SLA and routing rules |
| `citizen` | Citizen-facing complaint tickets (auth-only) |
| `public` | The public grievance intake form — **no login required** (see below) |
| `transport-masters` | Vehicle types, vehicles, trip attendance, fuel |
| `schedule-setup` | Collection points, staff templates, trip plans |
| `schedule-masters`, `reports` | **Legacy alias groups** — same underlying viewsets as `schedule-setup`/`schedule-operations`, kept because the seeded MainScreen data and the admin frontend still reference these names |
| `audits` | Login audit, common audit, staff audit |
| `localbody`, `districtbody`, `statebody` | Auth-only dashboard aggregates for the panchayat/district/state leader portals |
| `dashboard` | Operations dashboard summary |
| `operator-mobile` | Driver/operator mobile endpoints: today's trip, bin QR scan/validate, trip history/lifecycle |
| `waste-bluetooth` | Bluetooth weighing-device capture |
| `mobile` | Bare `login`/`waste` endpoints for the mobile app (no group prefix in the URL) |

You can see the live version of this list any time: start the server and
open `http://localhost:8000/api/v1/` — the custom router renders the groups
as a browsable index. Full docs with request/response shapes are at
`http://localhost:8000/api/v1/swagger/`.

### The `public` group has no auth — read this before touching it

`router.register_group("public", "publicgrievance", PublicGrievanceViewSet,
include_group_in_prefix=False)` produces a bare `/api/v1/publicgrievance/`
endpoint that any citizen can call **without logging in**, to report a waste
management issue from the public web form. It is the one deliberately
unauthenticated write path in this whole backend — be careful adding new
public endpoints to this group, and never register something here by
accident that should require a login.

## Scoping: geography, not company/project

**If you know the private backend, unlearn its multi-tenancy model here.**
Private scopes every table by `company` + `project` (multi-tenant SaaS
style). This backend has **no `location_scope_mixin.py`** — instead it
scopes data by **administrative geography**:

```text
State → District → Area Type → Local Body → Ward
                                  │
                    (exactly one of: Corporation,
                     Municipality, Town Panchayat,
                     Panchayat Union, Panchayat)
```

Most models carry a direct FK block (`state`, `district`, `area_type`, plus
whichever single local-body-level FK applies) rather than a `company_id`.
`app/utils/hierarchy.py` is the engine behind this:

- **`StaffDataScope`** (`app/models/superadmin/staff_management/staff_data_scope.py`)
  records which state/district/area-type/local-bodies/wards a given staff
  member may see — and supports many-to-many local-body scoping (one staff
  member can be granted several corporations/municipalities across
  different levels at once).
- **`filter_flat_geo_queryset_by_requester_scope()`** is the main
  "auto-scope this queryset to the logged-in user's permitted geography"
  helper, used across viewsets on the current flat-FK models.
- **Default-deny**: an authenticated non-superuser staff member with no
  resolvable `StaffDataScope` row gets an **empty queryset**, not
  unrestricted access. Superusers bypass scoping entirely.
- **A legacy closure-table model still exists** (`HierarchyNode` /
  `HierarchyClosure` / `HierarchyLevel`) for a shrinking set of models (like
  `CollectionPoint`) that still carry a `location_node` FK instead of the
  flat geo FKs. `filter_queryset_by_requester_scope()` handles those. The
  in-code comment marks this as deliberately being phased out — do not build
  new features on `location_node`; use the flat geo FKs.
- **`staff_scope_payload(user)`** builds the geography subtree (districts →
  area types → local bodies → wards, with staff rosters) embedded in the
  login response — this is what lets the leader-management dashboards know
  "which local bodies live under my boundary" without extra round-trips.

When you add a model that needs geography scoping, follow an existing model
in `masters/leader_management/` or `customer_masters/` rather than starting
from scratch — see [03-app-structure.md](03-app-structure.md).

## Where the moving parts live

| Concern | Location |
|---|---|
| Settings, database, CORS, email, OTP, Firebase | `config/settings.py` |
| Token lifetime and signing (access **and** refresh) | `config/settings_jwt.py` |
| Test-only settings (SQLite) | `config/test_settings.py` |
| Route table | `app/urls/base_urls.py` |
| Grouped router | `app/urls/custom_router.py` |
| Geography scoping engine | `app/utils/hierarchy.py` |
| Background/business logic | `app/services/` |
| Sample data | `app/management/commands/seed.py` |
| Nightly trip generation | `app/management/commands/generate_daily_trips.py`, wired via `scheduler.sh` |

Next: [02-database-and-env.md](02-database-and-env.md).
