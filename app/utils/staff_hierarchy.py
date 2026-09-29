"""Scope resolution for StaffHierarchy rows.

A StaffHierarchy row may be scoped to a place (country / state / district /
area type / one local body). A row *covers* an area when every scope column
it sets matches that area; blank columns match anything. For a role in a
given area, the covering row with the deepest scope wins — so a Panchayat
row overrides a District row, which overrides a State-wide one, which
overrides the unscoped default.
"""
from app.utils import ref_cache

LOCAL_BODY_SCOPE_FIELDS = (
    "corporation_id",
    "municipality_id",
    "town_panchayat_id",
    "panchayat_union_id",
    "panchayat_id",
)

# Broadest first.
SCOPE_FIELDS = (
    "country_id",
    "state_id",
    "district_id",
    "area_type_id",
    *LOCAL_BODY_SCOPE_FIELDS,
)

_SPECIFICITY = {
    "country_id": 1,
    "state_id": 2,
    "district_id": 3,
    "area_type_id": 4,
    **{field: 5 for field in LOCAL_BODY_SCOPE_FIELDS},
}

_MODELS = {
    "country_id": "app.models.superadmin.common_masters.country.Country",
    "state_id": "app.models.superadmin.common_masters.state.State",
    "district_id": "app.models.masters.district.District",
    "area_type_id": "app.models.masters.areatype.AreaType",
    "corporation_id": "app.models.masters.corporation.Corporation",
    "municipality_id": "app.models.masters.municipality.Municipality",
    "town_panchayat_id": "app.models.masters.town_panchayat.TownPanchayat",
    "panchayat_union_id": "app.models.masters.panchayat_union.PanchayatUnion",
    "panchayat_id": "app.models.masters.panchayat.Panchayat",
}

# Which parent columns each level's own record carries.
PARENT_FIELDS = {
    "state_id": ("country_id",),
    "district_id": ("country_id", "state_id"),
    "area_type_id": ("state_id", "district_id"),
    **{field: ("state_id", "district_id", "area_type_id") for field in LOCAL_BODY_SCOPE_FIELDS},
}

SCOPE_LEVEL_LABELS = {
    "country_id": "Country",
    "state_id": "State",
    "district_id": "District",
    "area_type_id": "Area Type",
    "corporation_id": "Corporation",
    "municipality_id": "Municipality",
    "town_panchayat_id": "Town Panchayat",
    "panchayat_union_id": "Panchayat Union",
    "panchayat_id": "Panchayat",
}

_NAME_ATTRS = {
    "corporation_id": "corporation_name",
    "municipality_id": "municipality_name",
    "town_panchayat_id": "town_panchayat_name",
    "panchayat_union_id": "union_name",
    "panchayat_id": "panchayat_name",
}


def _model(field):
    import importlib

    module_path, class_name = _MODELS[field].rsplit(".", 1)
    return getattr(importlib.import_module(module_path), class_name)


def scope_record(field, value):
    return ref_cache.get(_model(field), value) if value else None


def complete_geo(geo):
    """Return a copy of `geo` ({"<level>_id": unique_id}) with blank values
    dropped and missing parents filled in from the narrowest level upward
    (panchayat -> area type/district/state -> country)."""
    geo = {field: geo.get(field) for field in SCOPE_FIELDS if geo.get(field)}
    for field in reversed(SCOPE_FIELDS):
        if not geo.get(field) or field not in PARENT_FIELDS:
            continue
        record = scope_record(field, geo[field])
        for parent in PARENT_FIELDS[field]:
            value = getattr(record, parent, None)
            if value and not geo.get(parent):
                geo[parent] = value
    return geo


def row_scope(row):
    return {field: getattr(row, field) for field in SCOPE_FIELDS if getattr(row, field, None)}


def specificity(scope):
    return max((_SPECIFICITY[field] for field in scope), default=0)


def covers(scope, geo):
    return all(geo.get(field) == value for field, value in scope.items())


def resolve_entry(rows, role_id, geo):
    """The row in `rows` that decides `role_id`'s head within area `geo`
    (a completed geo dict), or None when no row covers it."""
    best = None
    for row in rows:
        if row.governmentusertype_id != role_id:
            continue
        scope = row_scope(row)
        if not covers(scope, geo):
            continue
        rank = (specificity(scope), len(scope))
        if best is None or rank > best[0]:
            best = (rank, row)
    return best[1] if best else None


def find_cycle(rows, pending):
    """True when saving `pending` (unsaved or edited, already swapped into
    `rows`) creates a reporting cycle in its own area or any narrower area
    that has its own rows, since those areas inherit `pending`."""
    pending_scope = row_scope(pending)
    areas = [pending_scope] + [
        scope
        for scope in (row_scope(row) for row in rows)
        if covers(pending_scope, scope)
    ]
    for area in areas:
        seen = set()
        current = pending.governmentusertype_id
        while current:
            if current in seen:
                return True
            seen.add(current)
            entry = resolve_entry(rows, current, area)
            current = entry.reports_to_governmentusertype_id if entry else None
    return False


def scope_label(row):
    """Human-readable scope, e.g. "Tamil Nadu › Erode › Rural › Kavindapadi"."""
    parts = []
    for field in SCOPE_FIELDS:
        value = getattr(row, field, None)
        if not value:
            continue
        record = scope_record(field, value)
        if record is None:
            parts.append(value)
        elif field == "area_type_id":
            parts.append(record.get_name_display())
        else:
            parts.append(getattr(record, _NAME_ATTRS.get(field, "name"), value))
    return " › ".join(parts)


def scope_level(row):
    scope = row_scope(row)
    if not scope:
        return None
    deepest = max(scope, key=lambda field: _SPECIFICITY[field])
    return SCOPE_LEVEL_LABELS[deepest]


# GovernmentStaffUserType.level -> the broader levels above it. Every local
# body — Panchayat Union and Panchayat alike — sits directly under its
# district, so a local-body role reports within its own level, or to
# District/State.
LEVEL_ANCESTORS = {
    "state": (),
    "district": ("state",),
    "corporation": ("district", "state"),
    "municipality": ("district", "state"),
    "town_panchayat": ("district", "state"),
    "panchayat_union": ("district", "state"),
    "panchayat": ("district", "state"),
}

_SCOPE_FIELD_LEVEL = {
    "state_id": "state",
    "district_id": "district",
    "area_type_id": "district",
    "corporation_id": "corporation",
    "municipality_id": "municipality",
    "town_panchayat_id": "town_panchayat",
    "panchayat_union_id": "panchayat_union",
    "panchayat_id": "panchayat",
}


def scope_government_level(scope):
    """Government level the scope sits at ("panchayat", "district", ...), or
    None for no scope / country-only (which admits every level)."""
    levels = [
        (_SPECIFICITY[field], _SCOPE_FIELD_LEVEL[field])
        for field in scope
        if field in _SCOPE_FIELD_LEVEL
    ]
    return max(levels)[1] if levels else None


def level_within(level, scope_level):
    """True when a role at `level` may be configured for an area at
    `scope_level`: only roles of exactly that level (a State location takes
    State roles, a Panchayat location Panchayat roles). No scope, or a
    country-only one, admits every level."""
    return scope_level is None or level == scope_level


def can_report_to(level, head_level):
    """True when a `level` role may report to a `head_level` role: the same
    level or a broader one above it."""
    return head_level == level or head_level in LEVEL_ANCESTORS.get(level, ())
