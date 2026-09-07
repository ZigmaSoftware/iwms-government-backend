# 03 — App Structure

Everything lives in `app/`. This file is a tour of each folder and how they
fit together, so you know where to put a new feature.

**If you're used to the private backend's flatter `superadmin_masters/` /
`masters/` / `waste_types/` layout, note that this repo reorganizes model,
serializer and viewset subfolders into a two-tier namespace** —
`superadmin/<subfolder>`, `masters/<subfolder>`, `core_modules/<subfolder>`
— rather than one folder per domain at the top level. Keep that in mind when
searching for a file by guessing its path from the private repo's shape.

## The shape of one feature

Adding a new master means touching the same five places as the private
backend, just nested one level deeper:

```text
app/models/masters/<subfolder>/thing.py          1. the table
app/serializers/masters/<subfolder>/thing.py     2. JSON in/out
app/viewsets/masters/<subfolder>/thing.py        3. the endpoint behaviour
app/urls/base_urls.py                            4. one register_group line
app/management/commands/seeders/masters/...      5. sample rows (optional)
tests/masters/...                                6. tests
```

Follow the same order for anything new. The quickest way to get it right is
to copy the nearest existing feature in the same subfolder and rename — the
conventions (audit fields, geography scoping, display IDs) are easy to miss
if you start from a blank file.

## `app/models/` — the database tables

```text
models/
├── superadmin/              staff, audits, common masters, role & screen
│   ├── audits/
│   ├── common_masters/
│   ├── role_management/
│   ├── screen_management/
│   ├── staff_management/       staffcreation.py, staff_data_scope.py
│   └── user_management/
├── superadmin_masters/      now nearly vestigial — just auth_user.py
│                            (the platform/company/project login user)
├── masters/
│   ├── customer_masters/
│   ├── leader_management/      state_leader_login.py, district_leader_login.py,
│   │                            panchayat_leader_login.py — the three
│   │                            leader-portal login models
│   ├── transport_masters/
│   └── waste_masters/          waste type / bin content lives here, not a
│                                top-level waste_types/ folder
├── core_modules/            government-specific business domain folder
│   ├── attendance/
│   ├── complaint_management/
│   ├── daily_operations/
│   ├── notifications/
│   └── schedule_setup/
├── reports/waste_reports/
└── waste_collection_bluetooth/
```

Two shared pieces almost every model uses, both in `app/utils/`:

- **`base_models.py`** — the base class giving every table its `unique_id`
  primary key plus the shared flags (`is_active`, `is_deleted`) and
  timestamps. The primary key is a **prefixed string**, not an auto-counting
  integer, so ids are readable in the API and stay unique across the whole
  system instead of colliding at `1, 2, 3`.
- **`audit_mixin.py` / `common_audit.py`** — records *who* created or
  changed a row, sourced from `RequestMetaMiddleware` — that middleware must
  stay enabled in `config/settings.py`.

`StaffDataScope` (`superadmin/staff_management/staff_data_scope.py`) is the
one worth knowing early: it is the geography-grant table that
`app/utils/hierarchy.py` reads to scope every list query. See
[01-architecture-overview.md](01-architecture-overview.md) for the full
scoping model.

## `app/serializers/` — validation and JSON shape

Mirrors the model folders exactly, same two-tier nesting. A serializer
decides which fields the API exposes, what is required, and any cross-field
rules. `app/validators/superadmin/screen_management/` holds dedicated
cross-field validators for the screen-permission system.

## `app/viewsets/` — the endpoints

Mirrors the model/serializer groups, plus portal- and audience-specific
folders the private backend doesn't have:

| Folder | Purpose |
|---|---|
| `superadmin/`, `masters/`, `core_modules/` | Standard CRUD per domain |
| `login/` | Login, **captcha**, my-permissions, refresh-token |
| `citizen_login/` | Citizen-facing login |
| `localbody/`, `districtbody/`, `statebody/` | Auth-only dashboard aggregates for each leader portal |
| `operator_mobile/` | Endpoints the driver/operator mobile screens call |
| `reports/` | Report generation |
| `waste_collection_bluetooth/` | Bluetooth weighing-device capture |
| a `public` group entry (`PublicGrievanceViewSet`) | The unauthenticated citizen grievance intake — see 01 |

Most CRUD viewsets are thin. When logic gets big it moves to
`app/services/`.

## `app/urls/` — how a viewset becomes a URL

- **`custom_router.py`** defines `GroupedRouter`, near-identical to the
  private backend's: `register_group(group, prefix, viewset, basename=None,
  include_group_in_prefix=True)` puts the group into the URL path, gives the
  route a predictable basename, and records the group so `/api/v1/` can
  render a browsable index. It additionally wires
  `register_group_basename()` into `app/utils/swagger.py`'s
  `GroupedSwaggerAutoSchema`, so Swagger's docs are grouped the same way the
  browsable API is (`SWAGGER_SETTINGS.DEFAULT_AUTO_SCHEMA_CLASS` in
  `config/settings.py`).
- **`base_urls.py`** is the route table — see
  [01-architecture-overview.md](01-architecture-overview.md) for the full
  group table. A few groups deliberately duplicate the same viewset under
  two names (`schedule-masters`/`reports` alias `schedule-setup` +
  `schedule-operations`) — that's not a bug, it's the admin frontend and the
  seeded MainScreen data still expecting the old names.

Adding an endpoint is one line:

```python
router.register_group("masters", "villages", VillageViewSet)
# -> /api/v1/masters/villages/
```

## `app/permissions/` and `app/middleware/`

- `middleware/module_permission_middleware.py` — a request-level gate: does
  this user's role have access to this module at all?
- `middleware/request_meta_middleware.py` — stores the current request/user
  so the audit mixin can stamp rows.

Screen- and column-level permissions are *data*, not code: they live in the
`screen_management` tables and are seeded by
`seeders/superadmin/screen_management/`.

## `app/services/`

Business logic too large for a thin viewset — trip scheduling, complaint
ticket routing, push notifications (`push_notification_service.py`, a
no-op until `FIREBASE_CREDENTIALS_PATH` is set), OpenRouteService calls.

## `app/utils/` — shared helpers

The ones you will reach for most:

| File | Use |
|---|---|
| `base_models.py`, `audit_mixin.py` | Base model and audit fields |
| `hierarchy.py` | The geography scoping engine — `StaffDataScope`, `filter_flat_geo_queryset_by_requester_scope()`, `staff_scope_payload()` (see 01) |
| `filters.py`, `pagination.py` | List filtering and paging |
| `swagger.py` | Keeps Swagger group names in step with the grouped router |

## `app/signals/` and `app/authentication/`

- `signals/` — react to model saves (e.g. regenerate permissions when a
  screen changes).
- `authentication/jwt.py` — the custom `JWTUserAuthentication` DRF
  authentication class wired into `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`.

Next: [04-commands-reference.md](04-commands-reference.md).
