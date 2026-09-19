# Geo-Hierarchy: ForeignKey → Plain UUID References

## What this is

Every model that used to reference the geo hierarchy (State, District,
AreaType, Corporation, Municipality, TownPanchayat, PanchayatUnion,
Panchayat, Continent, Country) — plus Ward, CustomerCreation, StaffTemplate,
VehicleCreation, TripPlan, ComplaintTicket, and ~30 other consumer models —
used to do so via a Django `ForeignKey`. All of those fields have been
converted to a plain `CharField(max_length=30)` holding the related row's
`unique_id` string. There is no `ForeignKey`, no DB-level relation, and no
`on_delete` behavior anywhere in this part of the schema anymore.

## Why

Real foreign keys tie the schema to Django's relational/ORM machinery
(join-based lookups, `on_delete` cascade/protect/set-null behavior, DB-level
referential integrity). That gets in the way when merging data from
third-party APIs: incoming rows may reference IDs that don't exist locally
yet, may need to be inserted out of order, or may need to bypass referential
checks entirely. A plain `unique_id` string has none of those constraints —
it's just a value, not a relationship the database enforces.

## Foreign Key vs. Plain UUID Reference

| | ForeignKey (old) | Plain UUID CharField (new) |
|---|---|---|
| **Field declaration** | `models.ForeignKey(Corporation, on_delete=models.PROTECT, related_name="wards")` | `models.CharField(max_length=30, null=True, blank=True)` |
| **Stored value** | Same thing either way — the target row's `unique_id` string | Same thing either way — the target row's `unique_id` string |
| **DB-level constraint** | Yes — the database enforces the referenced row exists | No — any string can be stored, valid or not |
| **`on_delete` behavior** | `PROTECT` / `CASCADE` / `SET_NULL` / `DO_NOTHING`, enforced by the DB | None. Deleting a "parent" row does nothing to children automatically — see [Cascade Soft-Delete](#cascade-soft-delete) below |
| **Attribute access** | `ward.corporation` returns a `Corporation` **instance** (triggers a query, or reuses a `select_related` join) | `ward.corporation_id` is just a **string** — `ward.corporation_id` *is* the unique_id, not an object |
| **Traversal (`obj.field.other_field`)** | Works: `ward.corporation.corporation_name` | Does **not** work — `ward.corporation_id` has no `.corporation_name`. Must look the object up explicitly: `Corporation.objects.filter(unique_id=ward.corporation_id).values_list("corporation_name", flat=True).first()` |
| **`select_related` / `prefetch_related`** | Works, reduces queries | Not applicable — there's no relation to select. `select_related("corporation")` on a converted field now raises `FieldError` |
| **ORM filtering by related object** | `Ward.objects.filter(corporation=some_corp_instance)` or `filter(corporation__corporation_name="X")` (joins) | `Ward.objects.filter(corporation_id=some_corp.unique_id)` — plain equality, no join. `corporation_id__corporation_name` is invalid (no relation to traverse) |
| **Reverse accessor** (`corporation.wards.all()`) | Auto-created by `related_name` | Does **not** exist automatically. Must query explicitly: `Ward.objects.filter(corporation_id=corporation.unique_id)`, or a hand-written `@property` that does the same (see below) |
| **Referential integrity** | Guaranteed by the DB | Not guaranteed — a `corporation_id` string can point at a row that was hard-deleted or never existed. The application is responsible for validity, not the schema |
| **Cross-system / third-party merge** | Hard — incoming rows need the referenced row to already exist locally, in the right order | Easy — any `unique_id` string can be stored regardless of insertion order or whether the row exists yet |

### The most common mistake this causes

Code written against the old FK fields often looks like this, and now
silently breaks or behaves incorrectly instead of raising an error:

```python
# BEFORE (FK): ward.corporation was a Corporation instance
name = ward.corporation.corporation_name          # worked

# AFTER (plain string): ward.corporation_id is just a string
name = ward.corporation_id.corporation_name        # AttributeError: 'str' has no attribute 'corporation_name'
```

The fix is always to resolve the id explicitly:

```python
from app.models.masters.corporation import Corporation

name = Corporation.objects.filter(
    unique_id=ward.corporation_id
).values_list("corporation_name", flat=True).first()
```

`app/utils/hierarchy.py` has shared helpers (`flat_geo_display`,
`_resolve_geo_candidate`, `normalize_flat_geo_attrs`) that do this
resolution consistently across serializers — prefer reusing those over
writing a fresh lookup every time.

## Cascade Soft-Delete

Removing `ForeignKey`s also removed the reverse-relation accessors
(`corporation.wards.all()`, etc.) that cascade soft-delete relies on — see
**[`CASCADE_SOFT_DELETE.md`](./CASCADE_SOFT_DELETE.md)** for the full
mechanism, what broke, and how it was fixed.
