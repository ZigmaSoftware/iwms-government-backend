# Cascading Soft-Delete — How It Works

This document explains the cascade soft-delete system built into the IWMS backend: what happens when you delete a record, how child records get swept up automatically, and exactly which files are responsible for which part of it.

---

## 1. The core idea in one paragraph

Nothing is ever hard-deleted (no `DELETE FROM` ever runs against real data through the app). "Deleting" a record means flipping two flags on it: `is_deleted = True` and `is_active = False`. The row stays in the database forever; every list/detail endpoint simply filters out rows where `is_deleted = True`. On top of that flag-flip, each model can declare a list of its own **direct children** — other tables that "live inside" it. When a record is deleted, the system automatically walks that list, flips the same two flags on every child, then looks at *those* children's own declared children, and keeps going — for as many levels as the chain goes. This is what makes deleting a Continent also delete every Country, State, District, Ward, Bin, Vehicle, Trip Plan, and so on underneath it, automatically, without any of that logic being hand-written per pair of tables.

---

## 2. Soft delete: the two flags

Every deletable table has:

| Field | Meaning |
|---|---|
| `is_deleted` | `True` once the record (or an ancestor of it) has been deleted. Every list/detail API filters `is_deleted=False`. |
| `is_active` | Set to `False` at the same time. Used for "Active/Inactive" toggles elsewhere in the UI; a deleted record is always inactive too. |
| `updated_by` | Stamped with the account that performed the delete (see §5), on every row touched — not just the one you clicked delete on. |

These three fields live on **`BaseMaster`**, an abstract base class that almost every model in the app inherits from.

**File:** `iwms-government-backend/app/utils/base_models.py`

```python
class BaseMaster(models.Model):
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    CASCADE_SOFT_DELETE = ()   # <-- each subclass overrides this with its own children

    created_by = models.ForeignKey(Account, ...)
    updated_by = models.ForeignKey(Account, ...)

    class Meta:
        abstract = True

    def delete(self, *args, updated_by=None, **kwargs):
        cascade_soft_delete(self, updated_by=updated_by)
```

Notice `delete()` here does **not** do `self.is_deleted = True; self.save()` directly — it hands off to `cascade_soft_delete()`, which is where all the real work happens. This means: **any model that inherits `BaseMaster` and calls `instance.delete()` automatically gets cascade behavior for free**, as long as it declares a `CASCADE_SOFT_DELETE` tuple (empty by default, meaning "no children, just delete me").

---

## 3. The cascade engine

**File:** `iwms-government-backend/app/utils/cascade_delete.py`

This file has two functions. This is the entire mechanism — everything else in the codebase just *declares data* that this file *acts on*.

### 3.1 `cascade_soft_delete(instance, updated_by=None)`

This is what actually performs the delete. Algorithm:

1. Start at the record being deleted (`instance`).
2. Look at `type(instance).CASCADE_SOFT_DELETE` — a tuple of strings. Each string is the name of a **reverse relation** on the model (i.e. `instance.<name>` gives you the related child rows) — or, for the many relations that no longer have a real reverse accessor (see §3.3), a name registered in `STRING_FK_CASCADE_RELATIONS`.
3. For each declared relation name, fetch the related object(s) via `_resolve_related_manager()`:
   - First, try `getattr(instance, rel_name)`, the normal Django path:
     - If it's a reverse ForeignKey or ManyToMany (a "manager" with `.all()`), iterate every row.
     - If it's a reverse **OneToOne** (a single object, not a list — e.g. a `DailyTripAssignment` has exactly one `DailyTripLog`), take that one object directly.
   - If that comes back empty (`None`), fall back to `STRING_FK_CASCADE_RELATIONS` (see §3.3) — if the relation name is registered there, run `child_model.objects.filter(filter_field=instance.unique_id)` to reconstruct the same set of children a reverse-FK manager would have returned, and iterate those.
4. For every child object found, **repeat the same process recursively** — look at *that child's own* `CASCADE_SOFT_DELETE`, and so on.
5. Every object visited is recorded in a `(model_class, primary_key)` set, so a row reachable by two different paths (e.g. a `Ward` reachable both directly from `State.wards` and indirectly via `State → District → Ward`) is only ever processed once.
6. Once the whole graph has been walked and nothing new is found, do the actual database writes: **one bulk `UPDATE ... SET is_deleted=True, is_active=False` per model type**, using all the primary keys collected for that model. If `updated_by` was passed in, it's included in the same bulk update, for every model that actually has an `updated_by` field.
7. All of this happens inside a single `transaction.atomic()` block — either the whole cascade succeeds, or none of it does (no partial cascades left dangling if something errors partway through).

Why bulk `UPDATE` instead of calling `.delete()` on each child one at a time? Performance (a Continent delete can touch thousands of rows across a dozen tables) — but the trade-off is that bulk `UPDATE` does **not** trigger Django signals or per-instance `save()`/`delete()` overrides. This is safe today because every model in the cascade only does a plain flag-flip on delete anyway (see §7 for the one place this trade-off actually matters).

### 3.2 `collect_cascade_cache_scopes(instance)`

A companion function used only for cache invalidation (not deletion itself). Many list/detail API endpoints are cached (see `app/cache/`), keyed by a "scope" name like `"continent_list"`. If deleting a Continent cascades into Wards and Bins, the cached `bins_list` response also needs to be invalidated — otherwise the UI would keep showing deleted bins until the cache naturally expires.

This function walks the exact same `CASCADE_SOFT_DELETE` graph as above, but instead of touching the database, it just collects every `CACHE_SCOPES` tuple declared on every model class it passes through, and returns the de-duplicated union. It's called **before** the actual delete (so it works even for models that end up with zero matching rows — it walks model *classes*, not query results). It resolves each declared relation name to its child model the same two-step way as §3.1: first a real Django field/reverse-relation lookup (`model._meta.get_field(rel_name)`), then `STRING_FK_CASCADE_RELATIONS` as a fallback.

### 3.3 `STRING_FK_CASCADE_RELATIONS` — the string-FK fallback registry

A separate, larger refactor (see [`geo_hierarchy_fk_removal.md`](./geo_hierarchy_fk_removal.md)) converted most `ForeignKey` fields across the location hierarchy and its consumer tables (Ward, Bins, VehicleCreation, StaffTemplate, TripPlan, ComplaintTicket, and ~30 others) into plain `CharField(max_length=30)` columns holding the related row's `unique_id` string, with no real database relation. That conversion **silently broke most of the cascade tree**: `getattr(instance, rel_name, None)` had always relied on the reverse-FK accessor Django auto-generates from `related_name` on a live `ForeignKey`. Once the child's field was no longer an FK, that accessor stopped existing — and because the lookup's default was `None` rather than raising, cascade-deleting e.g. a Corporation silently stopped reaching its Wards, Bins, Vehicles, StaffTemplates, TripPlans, ComplaintTickets, and most other consumer tables, with no error or log to say so.

The fix: `app/utils/cascade_delete.py` declares a registry —

```python
STRING_FK_CASCADE_RELATIONS = {
    ("app.models.masters.corporation.Corporation", "bins"):
        ("app.models.masters.waste_masters.bins.Bins", "corporation_id"),
    ("app.models.superadmin.common_masters.continent.Continent", "countries"):
        ("app.models.superadmin.common_masters.country.Country", "continent_id"),
    # ... ~190 entries covering every CASCADE_SOFT_DELETE relation broken by the FK removal
}
```

mapping `(declaring model dotted path, relation name) → (child model dotted path, filter field)` for every relation that used to be a real reverse-FK accessor and is now a plain string reference. Dotted paths (not direct imports) are used because `cascade_delete.py` is imported very early, from `BaseMaster` — importing the actual model classes at module load time would risk circular imports; `_lazy_model()` resolves a dotted path only when actually needed, via `_resolve_related_manager()` (§3.1) and `collect_cascade_cache_scopes()`'s `_resolve_child_model()` (§3.2).

Two relations — `wards` and `customer_creations` — are **not** in the registry, because those two already have working `@property` accessors defined directly on the geo models instead (e.g. `Corporation.wards` returns `Ward.objects.filter(corporation_id=self.unique_id)`). Either approach works identically as far as `cascade_soft_delete()` is concerned; the registry exists so the other ~190 relations didn't each need their own hand-written property method across 10 different model files.

**Adding a new registered relation** — when a new model is converted from `ForeignKey` to a plain `CharField`, or a new `CASCADE_SOFT_DELETE` entry is added that points at an already-converted model:

```python
_register(
    "app.models.masters.corporation.Corporation",   # declaring model (dotted path)
    "some_new_relation",                              # the name used in CASCADE_SOFT_DELETE
    "app.models.some_app.some_model.SomeModel",        # child model (dotted path)
    "corporation_id",                                  # field on the child that stores the parent's unique_id
)
```

Then verify nothing is left unresolved:

```python
from django.apps import apps
from app.utils.cascade_delete import STRING_FK_CASCADE_RELATIONS, _model_path

missing = []
for model in apps.get_models():
    for rel_name in getattr(model, "CASCADE_SOFT_DELETE", ()):
        has_real = True
        try:
            model._meta.get_field(rel_name)
        except Exception:
            has_real = False
        has_property = isinstance(getattr(model, rel_name, None), property)
        has_registry = (_model_path(model), rel_name) in STRING_FK_CASCADE_RELATIONS
        if not (has_real or has_property or has_registry):
            missing.append((model.__name__, rel_name))

assert not missing, missing
```

An empty `missing` list means cascade-delete will not silently skip any branch of the tree — this is also the authoritative way to check §4.1's relation lists are still accurate after any future model change, rather than trusting the table by eye.

---

## 4. Declaring children on a model

Every model that should sweep other records when it's deleted adds one line: a `CASCADE_SOFT_DELETE` class attribute, listing the `related_name` of each direct child relation.

**Rule of thumb: a model only needs to list its own *direct* children.** It does not need to know about its grandchildren — those cascade automatically because the child model lists *its* children in turn.

Example — the top of the location hierarchy:

```python
# app/models/superadmin/common_masters/continent.py
class Continent(BaseMaster):
    CASCADE_SOFT_DELETE = ("countries", "states", "districts")
```

```python
# app/models/superadmin/common_masters/country.py
class Country(BaseMaster):
    CASCADE_SOFT_DELETE = ("states", "districts")
```

Continent doesn't need to list `"wards"` or `"bins"` anywhere — deleting a Continent reaches Country → State → District → ... → Ward → Bin purely because each of those models lists its own next level down.

### 4.1 Every model that currently declares `CASCADE_SOFT_DELETE`

For `Continent`, `Country`, `State`, `District`, `AreaType`, `Corporation`,
`Municipality`, `TownPanchayat`, `PanchayatUnion`, and `Panchayat`, almost
every relation listed below is backed by `STRING_FK_CASCADE_RELATIONS`
(§3.3), not a real Django reverse-FK accessor — the children's own fields
(`corporation_id`, `state_id`, etc.) are plain `CharField`s, not
`ForeignKey`s. Only `wards` and `customer_creations` (via `@property`) and
`staff_access_configurations`/`scoped_staff` (via a still-live
`ManyToManyField`) resolve the "normal" way. `Ward`, `TripPlan`,
`StaffTemplate`, and `DailyTripAssignment`'s relations, by contrast, are all
real reverse-FK/OneToOne accessors, because their *children* still hold a
genuine `ForeignKey` back to them.

| Model | File | Declares as children |
|---|---|---|
| `Continent` | `app/models/superadmin/common_masters/continent.py` | countries, states, districts |
| `Country` | `app/models/superadmin/common_masters/country.py` | states, districts |
| `State` | `app/models/superadmin/common_masters/state.py` | districts, area_type, corporations, municipalities, town_panchayats, panchayat_unions, panchayat, wards, leader_logins, bins, vehicles, staff_templates, collection_points, trip_plans, trip_plan_collection_points, daily_trip_logs, daily_trip_collection_points, daily_trip_assignments, daily_trip_household_collections, vehicle_breakdowns, secondary_bin_collection_events, waste_collections, complaint_routing_rules, address_change_requests, complaint_tickets, scoped_staff, staff_members, userscreen_column_permissions, dashboard_widget_permissions, userscreenpermissions, customer_creations, staff_access_configurations |
| `District` | `app/models/masters/district.py` | (same shape as State, minus "districts" — District has no children one level further down besides AreaType/Corporation/etc.) |
| `AreaType` | `app/models/masters/areatype.py` | corporations, municipalities, town_panchayats, panchayat_unions, panchayats, wards, + the same ~20 consumer tables as State/District |
| `Corporation` | `app/models/masters/corporation.py` | wards, departments, + the ~19 consumer tables |
| `Municipality` | `app/models/masters/municipality.py` | wards + the ~18 consumer tables |
| `TownPanchayat` | `app/models/masters/town_panchayat.py` | wards + the ~18 consumer tables |
| `PanchayatUnion` | `app/models/masters/panchayat_union.py` | wards + the ~18 consumer tables |
| `Panchayat` | `app/models/masters/panchayat.py` | wards, leader_logins + the ~18 consumer tables |
| `Ward` | `app/models/masters/ward.py` | bins, bin_collection_events, waste_collections, customers, staff_access_configurations |
| `StaffTemplate` | `app/models/core_modules/schedule_setup/staff_template.py` | trip_plans, daily_trip_assignments |
| `TripPlan` | `app/models/core_modules/schedule_setup/trip_plan.py` | plan_collection_points, daily_trip_assignments |
| `DailyTripAssignment` | `app/models/core_modules/daily_operations/daily_trip_assignment.py` | trip_collection_points, trip_household_collections, secondary_bin_collection_events, waste_collections, daily_trip_log (OneToOne), vehicle_breakdown (OneToOne), retrip_requests, unassignedstaffpool |

`BlockPanchayatUnion` is part of the same visual hierarchy in the admin UI but does not exist as a real migrated table in this database (no `app_blockpanchayatunion` table) — it's intentionally excluded from all of the above.

### 4.2 What's deliberately *excluded*, and why

Not every relationship a model has is included in its `CASCADE_SOFT_DELETE` list. Three categories are always left out:

1. **Models with no `is_deleted` field.** `TripAttendance`, `AlternativeStaffTemplate`, and `StaffAudit` are genuine database tables, but they were never given soft-delete flags — there is nothing for the cascade to flip. Including them in a `CASCADE_SOFT_DELETE` tuple would crash. Audit/log-style tables in particular are meant to be permanent records and are excluded on purpose.
2. **Many-to-many relations.** `StaffDataScope.wards`, `TripPlan.wards`, `Collection_point.wards`, etc. are M2M links, not ownership. Soft-deleting the *target* of an M2M relationship doesn't make sense — the correct operation would be "unlink," which is a different, smaller action outside this system's scope.
3. **"Points back at a different, unrelated parent" relations.** A few reverse relations look like children but actually point at a *different* record than the one that logically owns them — for example, `DailyTripAssignment.carried_over_collection_points` (stops carried in *from* a different trip), `retrip_source_requests` and `breakdown_source` (references to whichever *other* assignment spawned this one as a continuation). These are excluded because cascading into them would incorrectly delete data belonging to an unrelated record.

---

## 5. Where the cascade actually gets triggered: viewsets

Declaring `CASCADE_SOFT_DELETE` on a model is only half the story — something still has to call `instance.delete()` when a user clicks Delete in the UI. That happens in each entity's Django REST Framework viewset.

**File:** `iwms-government-backend/app/utils/audit_mixin.py` — `AuditViewSetMixin.perform_destroy()`

```python
def perform_destroy(self, instance):
    previous_data = self._serialize_instance(instance)
    account = self._account_for_request_user()

    self.log_audit(self.request, instance=instance, previous_data=previous_data, new_data=None)

    delete_kwargs = {"updated_by": account} if account is not None else {}
    instance.delete(**delete_kwargs)
```

This is the single method that every entity's DELETE endpoint should ultimately call. It does two things beyond the delete itself:
- Writes an entry to **Common Audit** (and its mirrored **Staff Audit** ledger) recording what was deleted and by whom, *before* the delete happens (so the "previous state" is captured).
- Passes the acting user's `Account` into `instance.delete(updated_by=account)`, so `updated_by` gets stamped on every cascaded row, not just the top-level one.

Every hierarchy viewset (Continent, Country, State, District, AreaType, Corporation, Municipality, TownPanchayat, PanchayatUnion, Panchayat, Ward, StaffTemplate) overrides `perform_destroy` only to add cache invalidation, but still calls `super().perform_destroy(instance)` so the audit + cascade logic above always runs:

```python
# e.g. app/viewsets/superadmin/common_masters/continent_viewset.py
def perform_destroy(self, instance):
    scopes = collect_cascade_cache_scopes(instance)   # collected BEFORE delete
    super().perform_destroy(instance)                  # audit log + cascade delete
    invalidate_on_commit(*scopes)                       # clear every affected cache
```

**Files using this exact pattern:**
- `app/viewsets/superadmin/common_masters/continent_viewset.py`
- `app/viewsets/superadmin/common_masters/country_viewset.py`
- `app/viewsets/superadmin/common_masters/state_viewset.py`
- `app/viewsets/masters/district_viewset.py`
- `app/viewsets/masters/areatype_viewset.py`
- `app/viewsets/masters/corporation_viewset.py`
- `app/viewsets/masters/municipality_viewset.py`
- `app/viewsets/masters/town_panchayat_viewset.py`
- `app/viewsets/masters/panchayat_union_viewset.py`
- `app/viewsets/masters/panchayat_viweset.py` *(filename has a pre-existing typo — "viweset")*
- `app/viewsets/masters/ward_viewset.py`
- `app/viewsets/core_modules/schedule_setup/staff_template_viewset.py`

A handful of other viewsets across the app were also fixed to route their delete through `super().perform_destroy()` instead of calling `instance.delete()` directly or hand-flipping the flags themselves (both patterns silently skipped the audit log and — before this work — silently skipped the cascade too). That list includes: `block_panchayat_union_viewset.py`, `waste_masters/bins_viewset.py`, `waste_masters/subproperty_viewset.py`, `waste_masters/property_viewset.py`, `waste_masters/wastetype_viewset.py`, `customer_masters/customer_access_configuration_viewset.py`, `role_management/contractorusertype_viewset.py`, `role_management/governmentstaffusertype_viewset.py`, `role_management/staffusertype_viewset.py`, `role_management/usertype_viewset.py`, `screen_management/mainscreen_viewset.py`, `screen_management/mainscreentype_viewset.py`, `screen_management/userscreen_viewset.py`, `screen_management/userscreenaction_viewset.py`, `core_modules/schedule_setup/collection_point_viewset.py`.

---

## 6. Special cases: models with their own delete logic

A few models have business rules on delete that go beyond a plain flag-flip, so their viewsets don't just call `instance.delete()` — they do a manual, more careful version and then explicitly re-sync whatever else depended on the deleted row:

| File | What it does differently |
|---|---|
| `app/viewsets/core_modules/daily_operations/secondary_bin_collection_event_viewset.py` | Deleting a bin-collection scan doesn't just flip flags — it recomputes the linked `DailyTripCollectionPoint`'s status/weight (from whatever scan is now the most recent for that stop, or resets it to "Pending" if none remain), then re-syncs the trip's `DailyTripLog` total. See `_resync_trip_cp_after_delete()`. |
| `app/viewsets/core_modules/daily_operations/waste_collection_viewset.py` | Same idea for household waste collections: recomputes the linked `DailyTripHouseholdCollection` row and the trip log's household weight total. See `_resync_household_collection_after_delete()`. |
| `app/viewsets/core_modules/daily_operations/daily_trip_collection_point_viewset.py` | Deleting a collection point directly (not via a scan event) re-syncs the trip log the same way, and also fixes a related bug: recreating a stop from its trip-plan template after a delete now reuses a matching soft-deleted row instead of colliding with a database uniqueness constraint. |
| `app/viewsets/core_modules/daily_operations/daily_trip_assignment_viewset.py`, `daily_trip_log_viewset.py`, `vehicle_breakdown_viewset.py` | Each has a validation guard (e.g. "verified trip logs are read-only," "approved breakdowns cannot be deleted") before the flag-flip, and stamps `updated_by` manually since they don't go through the generic `BaseMaster.delete()` path. |

These exist because **the generic cascade only flips two flags** — it has no idea that deleting a bin-collection scan should also recompute someone else's cached weight total. Anything beyond "soft-delete this and its declared children" has to be written by hand in that specific viewset.

---

## 7. A real gotcha that was hit and fixed: reverse OneToOne relations

`DailyTripAssignment.CASCADE_SOFT_DELETE` includes `"daily_trip_log"` and `"vehicle_breakdown"` — but unlike every other entry in every other tuple, these two are **OneToOne** relations, not one-to-many. Accessing `assignment.daily_trip_log` returns a single `DailyTripLog` object directly (or raises an error if none exists) — it does **not** return a manager with an `.all()` method.

The first version of the cascade walker assumed every relation had `.all()`/`.iterator()`, and crashed with `AttributeError: 'DailyTripLog' object has no attribute 'iterator'` the first time a cascade actually reached one of these two relations (deleting a Panchayat that had assignments with trip logs underneath it).

**Fix, in `cascade_delete.py`:**
```python
def _resolve_related_manager(model, obj, rel_name):
    try:
        related = getattr(obj, rel_name, None)
    except ObjectDoesNotExist:
        return None                # OneToOne accessor with nothing linked
    if related is not None:
        return related

    entry = STRING_FK_CASCADE_RELATIONS.get((_model_path(model), rel_name))
    if entry is None:
        return None
    child_path, filter_field = entry
    child_model = _lazy_model(child_path)
    return child_model.objects.filter(**{filter_field: obj.unique_id})

# in _walk(obj):
related = _resolve_related_manager(model, obj, rel_name)
if related is None:
    continue
if hasattr(related, "all"):
    for child in related.all().iterator():   # reverse FK / M2M manager, or a registry-backed QuerySet
        _walk(child)
else:
    _walk(related)                             # reverse OneToOne — a single object
```

This is mentioned here specifically because it's one of two non-obvious wrinkles in an otherwise simple mechanism: **if you ever add a new `CASCADE_SOFT_DELETE` entry, check whether that relation is a OneToOne field** (`models.OneToOneField` on the child model) — if so, no special handling is needed on your end, the walker already accounts for it, but it's worth knowing why the code has that branch. The other wrinkle is §3.3's `STRING_FK_CASCADE_RELATIONS` fallback, for relations that no longer have a real Django accessor at all.

---

## 8. Verifying `updated_by` and the audit trail

Two things happen on every delete that go beyond just soft-deleting rows:

1. **`updated_by`** is stamped on every row the cascade touches (not just the record you clicked "Delete" on), so you can always tell who triggered a given soft-delete, even for rows deleted only as a side effect of a parent being deleted.
2. **Common Audit** (and its mirrored Staff Audit ledger) gets one entry per top-level delete action, capturing the full previous state of that record. This is what powers the "Common Audit" screen in Audits → Common Audit in the admin panel. Note: only the *top-level* deleted record gets its own audit-log entry — cascaded children are not individually logged to Common Audit (only their `is_deleted`/`is_active`/`updated_by` fields change; there's no separate audit row per cascaded child).

Both are implemented in `AuditViewSetMixin.perform_destroy()` (§5) and depend on the deleting viewset routing through `super().perform_destroy()` rather than calling `instance.delete()` directly.

---

## 9. Frontend: how "Delete" actually reaches the backend

**Component:** `iwms-government-frontend/src/components/common/RowActionsMenu.tsx`

This is the shared "kebab menu" (three-dot Actions button) used across ~50 list pages. It's a small, self-contained popover (not a third-party dropdown library) rendered via a React portal so it isn't visually clipped by table scroll containers. Its props:

```tsx
<RowActionsMenu
  onEdit={() => navigate(editPath(id))}      // omit to hide the Edit item
  onDelete={() => void handleDelete(id)}      // omit to hide the Delete item
  editLabel="Edit"
  deleteLabel="Delete"
  extraItems={[                                // any additional custom actions
    { label: "View Image", icon: <Icon/>, onClick: ..., disabled: bool, disabledReason: "..." }
  ]}
/>
```

- Items can be `disabled` (shown grayed-out with a tooltip explaining why, instead of being hidden) — used e.g. on Daily Trip Log's "Verify"/"Revert to draft" actions.
- The Delete item, when present, is styled in red and calls a `handleDelete(id)` function defined in that page, which follows the same pattern everywhere:

```tsx
const handleDelete = async (id: string) => {
  const confirmDelete = await Swal.fire({ title: "...", icon: "warning", showCancelButton: true, ... });
  if (!confirmDelete.isConfirmed) return;
  try {
    await someEntityApi.delete(id);                 // DELETE /api/v1/.../{id}/
    setRows((current) => current.filter((row) => row.unique_id !== id));  // remove from UI immediately
    Swal.fire({ icon: "success", ... });
  } catch (error) {
    Swal.fire("Error", "...", "error");
  }
};
```

`someEntityApi.delete(id)` is a generic HTTP client method (`src/helpers/admin/crudHelpers.ts`) that just issues `DELETE {resource}/{id}/` against the Django REST API — all the cascade/audit logic described above runs entirely on the backend in response to that one HTTP call. The frontend has no cascade logic of its own; it only removes the deleted row from its own local list state after the backend confirms success.

50 list pages currently use `RowActionsMenu` (location-hierarchy masters, transport/waste/schedule-setup/daily-operations pages, complaint management, staff/customer/screen/role management). A handful of pages were deliberately left on their original UI (no kebab menu) because they're audit trails, approve/reject workflows, or drill-down summary views with no real "Edit + Delete" concept — see the list in §11.

---

## 10. Worked example — deleting a Staff Template

To make the mechanism concrete, here's exactly what happens, file by file, when someone clicks Delete on a Staff Template that has active trips under it:

1. **Frontend** (`staffTemplateList.tsx`): user confirms the SweetAlert2 dialog → calls `staffTemplateApi.delete(id)` → `DELETE /api/v1/schedule-setup/staff-templates/{id}/`.
2. **DRF routing** hits `StaffTemplateViewSet.destroy()` (standard DRF `ModelViewSet.destroy()`, not overridden) → calls `self.perform_destroy(instance)`.
3. **`StaffTemplateViewSet.perform_destroy()`** (`app/viewsets/core_modules/schedule_setup/staff_template_viewset.py`):
   ```python
   def perform_destroy(self, instance):
       scopes = collect_cascade_cache_scopes(instance)
       super().perform_destroy(instance)
       invalidate_on_commit(*(set(STAFF_TEMPLATE_CACHE_SCOPES) | set(scopes)))
   ```
   `collect_cascade_cache_scopes` walks StaffTemplate → TripPlan → DailyTripAssignment → ... and gathers every `CACHE_SCOPES` tuple along the way, **before** anything is deleted.
4. `super().perform_destroy(instance)` resolves to **`AuditViewSetMixin.perform_destroy()`** (`app/utils/audit_mixin.py`): logs one Common Audit entry for the Staff Template, then calls `instance.delete(updated_by=account)`.
5. That resolves to **`BaseMaster.delete()`** (`app/utils/base_models.py`), which calls **`cascade_soft_delete(staff_template_instance, updated_by=account)`** in `app/utils/cascade_delete.py`.
6. The cascade walks: `StaffTemplate.trip_plans` → each `TripPlan` → its own `CASCADE_SOFT_DELETE` (`plan_collection_points`, `daily_trip_assignments`) → each `DailyTripAssignment` → its own `CASCADE_SOFT_DELETE` (`trip_collection_points`, `trip_household_collections`, `secondary_bin_collection_events`, `waste_collections`, `daily_trip_log`, `vehicle_breakdown`, `retrip_requests`, `unassignedstaffpool`).
7. Once the whole graph is walked, one bulk `UPDATE` runs per model type (`StaffTemplate`, `TripPlan`, `DailyTripAssignment`, `DailyTripCollectionPoint`, `DailyTripHouseholdCollection`, `BinCollectionEvent`, `WasteCollection`, `DailyTripLog`, `VehicleBreakdown`, `TripRetripRequest`, `UnassignedStaffPool`) — all inside one transaction.
8. Back in the viewset, `invalidate_on_commit(...)` clears every cache scope collected in step 3, so the now-deleted trip plans/assignments immediately disappear from every relevant list page, not just the Staff Template list.

Verified live: a real Staff Template with 14 active Daily Trip Assignments, 56 Daily Trip Collection Points, and 14 Daily Trip Household Collections underneath it was deleted through this exact path, and every one of those rows correctly flipped to `is_deleted=True` in a single request.

---

## 11. Pages that intentionally do *not* have Delete / a kebab menu

Not every list page fits an "Edit + Delete" model. These were deliberately left on their original UI:

- **No soft-delete field at all** — deleting would hard-delete: Trip Attendance, Alternative Staff Template list pages (only Edit shown).
- **Genuine audit/log trails, meant to be permanent**: Vehicle Trip Audit, Bin Load Log, Common Audit, Login Audit, Staff Audit, Staff Template Audit Log.
- **Approve/reject workflow pages, not plain CRUD**: Trip Retrip Request, Daily Trip Log kept its View/Verify/Draft actions (folded into a kebab menu, per a later request, but still no Delete — see §9).
- **Drill-down summary views with only a "View" action**: Apartment → Block → Flat → User drill-down, Base Collection ward/panchayat summary.
- **Fully inline-editable grids with no navigate/Edit/Delete concept**: App Modules (per-row Save button).

---

## 12. Quick reference — "if I want to add cascade support to a new model"

1. Confirm the model extends `BaseMaster` (has `is_deleted`/`is_active`). If it doesn't, it can't be safely added — either give it those fields via a migration, or leave it out.
2. Add a `CASCADE_SOFT_DELETE = (...)` tuple listing the exact `related_name` of each direct child relation. Verify each name with:
   ```python
   [f.name for f in YourModel._meta.get_fields() if f.is_relation and not f.concrete]
   ```
3. If the model has its own cache (`CACHE_SCOPES`), add that tuple too, so `collect_cascade_cache_scopes` picks it up.
4. Make sure the model's viewset's `perform_destroy` calls `super().perform_destroy(instance)` (via `AuditViewSetMixin`) rather than hand-rolling `instance.is_deleted = True; instance.save()` — otherwise neither the cascade nor the audit log will run.
5. Run `python manage.py check`, then run the verification snippet in §3.3 to confirm your new relation name resolves. This matters because a typo (or a relation whose FK has since been converted to a plain string and isn't yet registered) fails **silently**: `getattr(obj, rel_name, None)` just returns `None`, `STRING_FK_CASCADE_RELATIONS` has no matching entry either, and that branch is skipped — no crash, just a silently incomplete cascade. If the relation points at a model whose field is a plain `CharField` (not a live FK), add a `_register(...)` entry per §3.3 instead of expecting `getattr` to find it.
6. Test the actual delete against a row with real child data before trusting it, ideally through the real DRF viewset (not just calling `.delete()` in a shell), so cache invalidation and audit logging are exercised too.
