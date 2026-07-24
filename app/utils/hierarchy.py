from app.models.masters.hierarchy_tree import HierarchyClosure, HierarchyNode
from django.db.models import Q
from app.models.superadmin.user_management.staff_data_scope import StaffDataScope

# NOTE: The Hierarchy Tree/Level/Assignment admin UI and management API have
# been removed. HierarchyNode/HierarchyClosure themselves — and the helpers
# below that still query them — remain only because Collection_point and a
# handful of other masters still carry a live `location_node` FK to
# HierarchyNode. Migrating those remaining dependents onto flat geo FKs
# (like DailyTripLog/DailyWasteComparison/MonthlyWeightReport already are)
# is tracked as separate follow-up work; once done, this entire node-based
# section can be deleted along with the HierarchyNode/HierarchyLevel/
# HierarchyClosure models.

LOCATION_FIELD = "location_node"
LOCATION_QUERY_PARAMS = (
    "location_node",
    "location_node_id",
    "hierarchy_node",
    "hierarchy_node_id",
)


def _node_id(node_or_id):
    return getattr(node_or_id, "unique_id", node_or_id)


def descendant_ids(node_or_id):
    node_id = _node_id(node_or_id)
    if not node_id:
        return []
    return list(
        HierarchyClosure.objects.filter(
            ancestor_id=node_id,
            is_deleted=False,
            descendant__is_deleted=False,
        ).values_list("descendant_id", flat=True)
    )


def filter_queryset_by_hierarchy(queryset, params, field=LOCATION_FIELD):
    node_id = next((params.get(param) for param in LOCATION_QUERY_PARAMS if params.get(param)), None)
    if not node_id:
        return queryset
    ids = descendant_ids(node_id)
    if not ids:
        return queryset.none()
    return queryset.filter(**{f"{field}_id__in": ids})


def hierarchy_payload(obj):
    node = getattr(obj, LOCATION_FIELD, None)
    if not node:
        return {
            "location_node_id": None,
            "location_node_name": None,
            "location_level": None,
        }
    level = getattr(node, "level", None)
    return {
        "location_node_id": node.unique_id,
        "location_node_name": node.name,
        "location_level": getattr(level, "name", None),
    }


def requester_scope_node(user):
    """
    The hierarchy node a logged-in staff/government user is scoped to: their
    own ``location_node`` if set, else the node of their government role
    (``governmentusertype_id.location_node``). Returns None for identities
    with no location (e.g. platform super admins), meaning "unscoped".
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    node = getattr(user, "location_node", None)
    if node:
        return node

    govt_type = getattr(user, "governmentusertype_id", None)
    return getattr(govt_type, "location_node", None) if govt_type else None


def _is_staff_user(user):
    """True when `user` resolves to a staff record (has a staff_unique_id),
    regardless of whether they have a StaffDataScope row."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "staff_unique_id", None):
        return True
    staff = getattr(user, "staff", None)
    return bool(getattr(staff, "staff_unique_id", None))


def _unscoped_result(queryset, user):
    """Fallback applied when the requester has no resolvable StaffDataScope.

    Super admins (``is_superuser``) see everything. Any other authenticated
    staff user is denied by default with an empty queryset (G4) so that a
    missing scope row can never silently grant global visibility. Anonymous /
    non-staff / internal callers keep the queryset unchanged — these scoped
    endpoints already sit behind the auth middleware.
    """
    if getattr(user, "is_superuser", False):
        return queryset
    if _is_staff_user(user):
        return queryset.none()
    return queryset


def _staff_scope(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    staff_id = getattr(user, "staff_unique_id", None)
    if not staff_id:
        staff = getattr(user, "staff", None)
        staff_id = getattr(staff, "staff_unique_id", None)
    if not staff_id:
        return None
    return (
        StaffDataScope.objects.filter(
            staff_id=staff_id,
            is_active=True,
            is_deleted=False,
        )
        .prefetch_related(
            "location_nodes",
            "corporations",
            "municipalities",
            "town_panchayats",
            "panchayat_unions",
            "panchayats",
            "wards",
        )
        .select_related("state", "district", "area_type")
        .first()
    )


FLAT_GEO_LEVEL_CANDIDATES = (
    ("panchayat", "panchayat_name", "Panchayat"),
    ("panchayat_union", "panchayat_union_name", "Panchayat Union"),
    ("town_panchayat", "town_panchayat_name", "Town Panchayat"),
    ("municipality", "municipality_name", "Municipality"),
    ("corporation", "corporation_name", "Corporation"),
    ("district", "name", "District"),
    ("state", "name", "State"),
)


def flat_geo_display(obj):
    """Display-friendly (name, level_label) for `obj`'s most specific
    populated geo field, e.g. a CustomerCreation scoped to a Corporation
    returns (corporation_name, "Corporation"). Returns (None, None) if no
    geo field is set."""
    if not obj:
        return None, None
    for field, name_attr, level_label in FLAT_GEO_LEVEL_CANDIDATES:
        candidate = getattr(obj, field, None)
        if not candidate:
            continue
        name = getattr(candidate, name_attr, None)
        if name:
            return name, level_label
    return None, None


def node_ids_for_flat_geo(obj):
    """Resolve HierarchyNode unique_ids matching the most specific populated
    geo field on `obj` (an object with state/district/area_type/corporation/
    municipality/town_panchayat/panchayat_union/panchayat FKs, e.g. a
    StaffDataScope or CustomerCreation row) by name lookup against the
    mirrored hierarchy tree. Returns [] if nothing resolves."""
    if not obj:
        return []

    candidates = [
        (getattr(obj, "panchayat", None), "panchayat_name"),
        (getattr(obj, "panchayat_union", None), "panchayat_union_name"),
        (getattr(obj, "town_panchayat", None), "town_panchayat_name"),
        (getattr(obj, "municipality", None), "municipality_name"),
        (getattr(obj, "corporation", None), "corporation_name"),
        (getattr(obj, "district", None), "name"),
        (getattr(obj, "state", None), "name"),
    ]
    for candidate, name_attr in candidates:
        if not candidate:
            continue
        name = getattr(candidate, name_attr, None)
        if not name:
            continue
        node_ids = list(
            HierarchyNode.objects.filter(
                name__iexact=name,
                is_deleted=False,
            ).values_list("unique_id", flat=True)
        )
        if node_ids:
            return node_ids
    return []


def node_for_flat_geo(obj):
    """Single best-matching HierarchyNode for `obj`'s most specific populated
    geo field (see `node_ids_for_flat_geo`), or None."""
    node_ids = node_ids_for_flat_geo(obj)
    if not node_ids:
        return None
    return HierarchyNode.objects.filter(unique_id__in=node_ids, is_deleted=False).first()


FLAT_GEO_SOURCE_TYPE_FIELDS = {
    "state": "state",
    "district": "district",
    "areatype": "area_type",
    "corporation": "corporation",
    "municipality": "municipality",
    "town_panchayat": "town_panchayat",
    "panchayat_union": "panchayat_union",
    "panchayat": "panchayat",
}


FLAT_GEO_FIELDS = (
    "state",
    "district",
    "area_type",
    "corporation",
    "municipality",
    "town_panchayat",
    "panchayat_union",
    "panchayat",
)

FLAT_GEO_QUERY_FIELDS = tuple(f"{field}_id" for field in FLAT_GEO_FIELDS)

LOCAL_BODY_FIELDS = (
    "corporation",
    "municipality",
    "town_panchayat",
    "panchayat_union",
    "panchayat",
)

# `StaffDataScope`'s local-body levels are many-to-many (a staff can be
# scoped to several corporations/municipalities/etc at once). Each tuple is
# (level name, single-value FK field name as carried by other flat-geo
# models like TripPlan/CustomerCreation, the M2M attribute on StaffDataScope).
STAFF_LOCAL_BODY_M2M_LEVELS = (
    ("corporation", "corporation_id", "corporations"),
    ("municipality", "municipality_id", "municipalities"),
    ("town_panchayat", "town_panchayat_id", "town_panchayats"),
    ("panchayat_union", "panchayat_union_id", "panchayat_unions"),
    ("panchayat", "panchayat_id", "panchayats"),
)


def validate_wards_for_flat_geo(wards, attrs, instance=None):
    """
    Validate that every selected Ward belongs to the record's effective local
    body.  ``attrs`` uses serializer source names (``corporation`` rather than
    ``corporation_id``); values omitted by PATCH are read from ``instance``.

    Returns an error string, or ``None`` when all wards match.
    """
    selected_field = next(
        (
            field
            for field in LOCAL_BODY_FIELDS
            if _resolve_geo_value(attrs, instance, field)
        ),
        None,
    )
    if not selected_field:
        return "Select a local body before selecting a ward."

    selected_body = _resolve_geo_value(attrs, instance, selected_field)
    selected_pk = _object_pk(selected_body)
    for ward in wards:
        if _object_pk(getattr(ward, selected_field, None)) != selected_pk:
            return (
                f"Ward '{ward.ward_name}' does not belong to the selected "
                f"{selected_field.replace('_', ' ')}."
            )
    return None


def filter_flat_geo_queryset_by_params(queryset, params, prefix=""):
    """
    Apply explicit state/district/area_type/local-body query params to a
    queryset that has flat geo FK columns. `prefix` supports related models,
    e.g. prefix="trip_assignment_id__" for VehicleBreakdown.
    """
    for field in FLAT_GEO_QUERY_FIELDS:
        value = params.get(field)
        if value:
            queryset = queryset.filter(**{f"{prefix}{field}": value})
    return queryset


def _object_pk(value):
    return getattr(value, "pk", value)


def _same_fk(left, right):
    return _object_pk(left) == _object_pk(right)


def _resolve_geo_value(attrs, instance, field):
    if field in attrs:
        return attrs.get(field)
    return getattr(instance, field, None) if instance else None


def normalize_flat_geo_attrs(attrs, instance=None, require_geo=False):
    """
    Normalize serializer attrs carrying flat geo FKs. If a corporation/
    municipality/town_panchayat/panchayat_union/panchayat is selected, copy
    its state, district, and area_type onto the attrs and reject contradictory
    parent selections. Returns an error dict; an empty dict means attrs were
    normalized successfully.
    """
    selected_local_bodies = [
        field for field in LOCAL_BODY_FIELDS
        if _resolve_geo_value(attrs, instance, field)
    ]

    if len(selected_local_bodies) > 1:
        return {
            "non_field_errors": (
                "Select only one local body: corporation, municipality, "
                "town_panchayat, panchayat_union, or panchayat."
            )
        }

    local_body = (
        _resolve_geo_value(attrs, instance, selected_local_bodies[0])
        if selected_local_bodies
        else None
    )

    if local_body:
        for parent in ("state", "district", "area_type"):
            parent_obj = getattr(local_body, f"{parent}_id", None)
            if not parent_obj:
                continue

            current = attrs.get(parent)
            if parent in attrs and current and not _same_fk(current, parent_obj):
                return {
                    f"{parent}_id": (
                        f"Selected {parent.replace('_', ' ')} does not match "
                        "the selected local body."
                    )
                }
            attrs[parent] = parent_obj

    district = _resolve_geo_value(attrs, instance, "district")
    area_type = _resolve_geo_value(attrs, instance, "area_type")
    state = _resolve_geo_value(attrs, instance, "state")

    if area_type:
        if "district" in attrs and district and not _same_fk(district, getattr(area_type, "district_id", None)):
            return {"district_id": "Selected district does not match the selected area type."}
        if "state" in attrs and state and not _same_fk(state, getattr(area_type, "state_id", None)):
            return {"state_id": "Selected state does not match the selected area type."}
        if "district" not in attrs:
            attrs["district"] = getattr(area_type, "district_id", None)
        if "state" not in attrs:
            attrs["state"] = getattr(area_type, "state_id", None)
    elif district:
        if "state" in attrs and state and not _same_fk(state, getattr(district, "state_id", None)):
            return {"state_id": "Selected state does not match the selected district."}
        if "state" not in attrs:
            attrs["state"] = getattr(district, "state_id", None)

    has_geo = any(_resolve_geo_value(attrs, instance, field) for field in FLAT_GEO_FIELDS)
    if require_geo and not has_geo:
        return {"district_id": "A staff template must be assigned to a geographic hierarchy."}

    return {}


def copy_flat_geo(target, source, only_empty=False):
    """Copy state/district/area_type/.../panchayat FKs from `source` onto
    `target`. Both models are expected to carry the same flat geo FK set
    (e.g. CustomerCreation -> TripPlan, or any two models in the
    Staff/Customer/TripPlan family). If `source` doesn't have these fields
    but has a `location_node` instead (e.g. Collection_point, which keeps
    a real HierarchyNode), the fields are derived from that node's mirrored
    ancestry via `flat_geo_fields_for_node`. Clears every field on `target`
    first unless `only_empty` is set and `target` already has a district.
    """
    if only_empty and getattr(target, "district_id", None):
        return

    if any(hasattr(source, field) for field in FLAT_GEO_FIELDS):
        values = {field: getattr(source, f"{field}_id", None) for field in FLAT_GEO_FIELDS}
    else:
        node = getattr(source, LOCATION_FIELD, None)
        values = {field: None for field in FLAT_GEO_FIELDS}
        values.update(flat_geo_fields_for_node(node))

    for field, value in values.items():
        setattr(target, f"{field}_id", value)


def sync_staff_data_scope(staff, source):
    """Give a staff user a `StaffDataScope` row matching `source`'s flat geo.

    The scoped viewsets (schedule-masters, waste, etc.) deny any non-super staff
    user that has NO StaffDataScope row by default (empty queryset — see
    `filter_flat_geo_queryset_by_requester_scope`). Seeded mobile logins
    (driver/supervisor) were created without one, so they could authenticate but
    saw ZERO trips / collection points / waste-graph data. Scoping them to the
    same flat geo their trip carries restores visibility while keeping the
    corporation/district boundary intact. Idempotent (update_or_create).

    `source` is any model carrying the flat geo FK block (a DailyTripAssignment,
    TripPlan, etc.). `staff` must expose `staff_unique_id`.
    """
    scope, created = StaffDataScope.objects.update_or_create(
        staff_id=staff.staff_unique_id,
        is_deleted=False,
        defaults={
            "state_id": getattr(source, "state_id", None),
            "district_id": getattr(source, "district_id", None),
            "area_type_id": getattr(source, "area_type_id", None),
            "is_active": True,
        },
    )
    for _, source_field, m2m_field in STAFF_LOCAL_BODY_M2M_LEVELS:
        value = getattr(source, source_field, None)
        getattr(scope, m2m_field).set([value] if value else [])
    return scope, created


def flat_geo_fields_for_node(node):
    """Reverse of `node_for_flat_geo`: given a HierarchyNode mirrored from a
    legacy geo master, walk its full ancestor chain (self included) and
    return a dict of every state/district/area_type/.../panchayat FK value
    mirrored along that chain, e.g. a panchayat node resolves state, district,
    area_type, AND panchayat together - not just the node's own level. Suitable
    for assigning directly onto a model with matching FK fields:
    `for field, value in flat_geo_fields_for_node(node).items():
        setattr(customer, f"{field}_id", value)`
    Returns {} for nodes with no mirrored ancestry (e.g. manually-created nodes).
    """
    if not node:
        return {}
    node_id = _node_id(node)
    links = HierarchyClosure.objects.filter(
        descendant_id=node_id, is_deleted=False
    ).select_related("ancestor")

    fields = {}
    for link in links:
        ancestor = link.ancestor
        if not ancestor or ancestor.is_deleted:
            continue
        props = getattr(ancestor, "custom_properties", None) or {}
        source_type = props.get("source_type")
        source_id = props.get("source_id")
        field = FLAT_GEO_SOURCE_TYPE_FIELDS.get(source_type)
        if field and source_id:
            fields[field] = source_id
    return fields


def _node_ids_for_geo_scope(scope):
    if not scope:
        return []

    direct_ids = list(scope.location_nodes.values_list("unique_id", flat=True))
    if direct_ids:
        return direct_ids

    return node_ids_for_flat_geo(scope)


def filter_queryset_by_requester_scope(queryset, user, field=LOCATION_FIELD):
    """
    Auto-scope a queryset to the requester's own node + descendants. Users
    with no resolvable scope node (e.g. super admins) see everything.
    """
    scope_node_ids = _node_ids_for_geo_scope(_staff_scope(user))
    if scope_node_ids:
        ids = set()
        for node_id in scope_node_ids:
            ids.update(descendant_ids(node_id))
        if not ids:
            return queryset.none()
        return queryset.filter(**{f"{field}_id__in": list(ids)})

    node = requester_scope_node(user)
    if not node:
        return _unscoped_result(queryset, user)
    ids = descendant_ids(node)
    if not ids:
        return queryset.none()
    return queryset.filter(**{f"{field}_id__in": ids})


STAFF_GEO_LEVEL_FIELDS = (
    "panchayat_id",
    "panchayat_union_id",
    "town_panchayat_id",
    "municipality_id",
    "corporation_id",
    "district_id",
    "state_id",
)


def filter_staff_queryset_by_requester_scope(queryset, user):
    """
    Auto-scope a `StaffcreationOfficeDetails` queryset to the requester's own
    geo scope (state/district/area_type/local-body, from their `StaffDataScope`
    row) plus everything beneath it. Mirrors `filter_queryset_by_requester_scope`
    but compares against the target staff rows' own state/district/.../panchayat
    columns instead of a shared `location_node`, since staff no longer carries
    a hierarchy node reference.
    """
    return filter_flat_geo_queryset_by_requester_scope(queryset, user)


LOCAL_BODY_SCOPE_FIELDS = {scope_field for _, scope_field, _ in STAFF_LOCAL_BODY_M2M_LEVELS}
M2M_FIELD_BY_SCOPE_FIELD = {
    scope_field: m2m_field for _, scope_field, m2m_field in STAFF_LOCAL_BODY_M2M_LEVELS
}


def _narrow_by_ward(queryset, scope):
    """
    Further restrict `queryset` to the requester's selected Wards, when both
    the requester has any Wards in scope AND the target model actually
    carries ward-level granularity. A no-op otherwise — Ward is an optional
    extra narrowing on top of the local-body/district scope, never a
    widening, so it's safe to apply speculatively across every scoped
    queryset in the app. Detects both conventions in use: a singular `ward`
    FK (Bins, CustomerCreation, ...) and a plural `wards` M2M (TripPlan).
    """
    ward_ids = list(scope.wards.values_list("unique_id", flat=True))
    if not ward_ids:
        return queryset

    model = queryset.model
    try:
        field = model._meta.get_field("ward")
    except Exception:
        field = None
    if field is not None:
        if field.many_to_many:
            return queryset.filter(ward__unique_id__in=ward_ids).distinct()
        return queryset.filter(ward_id__in=ward_ids)

    try:
        model._meta.get_field("wards")
    except Exception:
        return queryset
    return queryset.filter(wards__unique_id__in=ward_ids).distinct()


def filter_flat_geo_queryset_by_requester_scope(queryset, user, field_map=None):
    """
    Auto-scope a queryset whose model carries its own flat geo FKs (e.g.
    Corporation/Municipality/.../Panchayat, or any model with matching
    state_id/district_id/.../panchayat_id columns) to the requester's
    `StaffDataScope`. A staff scoped to one or more specific local bodies
    (across one or several levels — e.g. two Corporations and a
    Municipality at once) sees the union of every local body they were
    granted; one scoped only to a District sees everything within it. A
    Ward selection further narrows whichever rows that produces (see
    `_narrow_by_ward`).

    `field_map` lets a model whose columns don't match `STAFF_GEO_LEVEL_FIELDS`
    verbatim supply its own {scope_field: queryset_field} pairs. Super admins
    see everything; a non-super staff user with no scope row is denied by
    default (empty queryset) — see `_unscoped_result` (G4).
    """
    scope = _staff_scope(user)
    if not scope:
        return _unscoped_result(queryset, user)

    fields = field_map or {f: f for f in STAFF_GEO_LEVEL_FIELDS}
    direct_node_ids = list(scope.location_nodes.values_list("unique_id", flat=True))
    if direct_node_ids:
        combined_filter = Q()
        for node_id in direct_node_ids:
            node = HierarchyNode.objects.filter(unique_id=node_id, is_deleted=False).first()
            node_fields = flat_geo_fields_for_node(node)
            if not node_fields:
                continue
            node_filter = Q()
            has_filter = False
            for scope_field, queryset_field in fields.items():
                flat_field = scope_field[:-3] if scope_field.endswith("_id") else scope_field
                value = node_fields.get(flat_field)
                if value:
                    node_filter &= Q(**{queryset_field: value})
                    has_filter = True
            if has_filter:
                combined_filter |= node_filter
        if combined_filter:
            return _narrow_by_ward(queryset.filter(combined_filter), scope)
        return queryset.none()

    local_body_filter = Q()
    has_local_body_filter = False
    for scope_field, queryset_field in fields.items():
        if scope_field not in LOCAL_BODY_SCOPE_FIELDS:
            continue
        m2m_field = M2M_FIELD_BY_SCOPE_FIELD.get(scope_field)
        if not m2m_field:
            continue
        ids = list(getattr(scope, m2m_field).values_list("unique_id", flat=True))
        if ids:
            local_body_filter |= Q(**{f"{queryset_field}__in": ids})
            has_local_body_filter = True
    if has_local_body_filter:
        return _narrow_by_ward(queryset.filter(local_body_filter), scope)

    for scope_field, queryset_field in fields.items():
        if scope_field in LOCAL_BODY_SCOPE_FIELDS:
            continue
        try:
            attname = scope._meta.get_field(scope_field).attname
        except Exception:
            attname = scope_field
        value = getattr(scope, attname, None)
        if value:
            return _narrow_by_ward(queryset.filter(**{queryset_field: value}), scope)

    return _narrow_by_ward(queryset, scope)


def _single_local_body(scope):
    """
    The requester's (local_body_type, local_body_id) permission-ownership
    key, populated ONLY when the staff is scoped to exactly one local body
    in total across every level. A staff scoped to zero or several local
    bodies falls back to their District/State boundary for permission
    purposes instead (screens/dashboard widgets are governed by the
    broader geo boundary in that case, not an ambiguous or merged set of
    local-body-specific configs). Mirrors the identical rule applied in
    `staff_access_configuration_serializer._access_scope_payload`.
    """
    candidates = []
    for level, _, m2m_field in STAFF_LOCAL_BODY_M2M_LEVELS:
        for local_body_id in getattr(scope, m2m_field).values_list("unique_id", flat=True):
            candidates.append((level, local_body_id))
    if len(candidates) == 1:
        return candidates[0]
    return None, None


def local_body_scope_for_staff(user):
    """
    Derive the requester's effective Local Body ownership key
    (local_body_type, local_body_id) plus state/district/area_type, from
    their `StaffDataScope` row. Mirrors the derivation used for
    `localBodyLevel`/`localBodyId` in
    `staff_access_configuration_serializer._access_scope_payload`.

    Returns None if the requester has no resolvable data scope.
    """
    scope = _staff_scope(user)
    if not scope:
        return None

    local_body_type, local_body_id = _single_local_body(scope)

    return {
        "state_unique_id": scope.state_id,
        "district_unique_id": scope.district_id,
        "area_type_unique_id": scope.area_type_id,
        "local_body_type": local_body_type,
        "local_body_id": local_body_id,
    }


def staff_scope_payload(user):
    """
    JSON-safe summary of the requester's `StaffDataScope`, for embedding in
    the login response so the frontend knows which geography to display.
    Returns None when the user has no active scope row (unscoped/full access).
    """
    scope = _staff_scope(user)
    if not scope:
        return None

    def _ref(obj, name_attr):
        if not obj:
            return None
        return {"unique_id": obj.unique_id, "name": getattr(obj, name_attr, None)}

    local_body_name_attrs = {
        "corporations": "corporation_name",
        "municipalities": "municipality_name",
        "town_panchayats": "town_panchayat_name",
        "panchayat_unions": "union_name",
        "panchayats": "panchayat_name",
    }
    local_body_lists = {
        m2m_field: [
            _ref(obj, local_body_name_attrs[m2m_field]) for obj in getattr(scope, m2m_field).all()
        ]
        for _, _, m2m_field in STAFF_LOCAL_BODY_M2M_LEVELS
    }

    return {
        "state": _ref(scope.state, "name"),
        "district": _ref(scope.district, "name"),
        "area_type": _ref(scope.area_type, "name"),
        # Backward-compatible single value — the first selected local body of
        # each level — so existing consumers (every form that locks a field
        # to the staff's own single corporation/etc via scopeOption()) keep
        # working unchanged. The plural `*s` lists below carry the full set.
        "corporation": (local_body_lists["corporations"] or [None])[0],
        "municipality": (local_body_lists["municipalities"] or [None])[0],
        "town_panchayat": (local_body_lists["town_panchayats"] or [None])[0],
        "panchayat_union": (local_body_lists["panchayat_unions"] or [None])[0],
        "panchayat": (local_body_lists["panchayats"] or [None])[0],
        "corporations": local_body_lists["corporations"],
        "municipalities": local_body_lists["municipalities"],
        "town_panchayats": local_body_lists["town_panchayats"],
        "panchayat_unions": local_body_lists["panchayat_unions"],
        "panchayats": local_body_lists["panchayats"],
        "wards": [_ref(ward, "ward_name") for ward in scope.wards.all()],
        "location_nodes": [
            {"unique_id": node.unique_id, "name": node.name}
            for node in scope.location_nodes.all()
        ],
        # --- Scope expansion (login feature) -------------------------------
        # The level at which the scope was granted (most-specific field set)
        # plus the full geo subtree beneath it, so the frontend knows which
        # ULBs/RLBs (and their staff) live under the granted boundary without
        # extra round-trips. See `expanded_scope_payload`.
        "granted_level": _granted_scope_level(scope),
        "descendants": _expanded_descendants(scope),
    }


# ============================================================
# Downstream scope expansion (login response)
# ============================================================

# Human-friendly grouping for the two AreaType names.
AREA_TYPE_GROUP = {
    "Urban Local Body": "urban",
    "Rural Local Body": "rural",
}


def _local_body_ids_by_level(scope):
    """{level: [unique_ids]} for every local-body level with at least one
    selection, e.g. a staff scoped to two Corporations and one Municipality
    returns {"corporation": [...2 ids...], "municipality": [...1 id...]}.
    Levels with no selection are omitted."""
    result = {}
    for level, _, m2m_field in STAFF_LOCAL_BODY_M2M_LEVELS:
        ids = list(getattr(scope, m2m_field).values_list("unique_id", flat=True))
        if ids:
            result[level] = ids
    return result


def _granted_scope_level(scope):
    """The level at which `scope` was granted: local body if any is
    selected (regardless of how many, or across how many levels), else
    district, else state. Returns None for an all-null scope row."""
    if not scope:
        return None
    if _local_body_ids_by_level(scope):
        return "local_body"
    if scope.district_id:
        return "district"
    if scope.state_id:
        return "state"
    return None


def _expanded_descendants(scope):
    """Build the geo subtree beneath a StaffDataScope, grouped
    ``district -> area_type -> local_body (+ staff)``. Anchored at whatever
    level the scope was granted (state expands all districts; a single town
    panchayat expands only itself). Batched — a bounded, constant number of
    queries regardless of subtree size (no N+1). Returns ``{"districts": [...]}``.
    """
    if not scope:
        return None

    from app.models.masters.district import District
    from app.models.masters.areatype import AreaType
    from app.models.masters.corporation import Corporation
    from app.models.masters.municipality import Municipality
    from app.models.masters.town_panchayat import TownPanchayat
    from app.models.masters.panchayat_union import PanchayatUnion
    from app.models.masters.panchayat import Panchayat

    lb_models = {
        "corporation": (Corporation, "corporation_name"),
        "municipality": (Municipality, "municipality_name"),
        "town_panchayat": (TownPanchayat, "town_panchayat_name"),
        "panchayat_union": (PanchayatUnion, "union_name"),
        "panchayat": (Panchayat, "panchayat_name"),
    }

    state_id = scope.state_id
    district_id = scope.district_id
    area_type_id = scope.area_type_id

    # Every local body selected, grouped by level — a staff can now be
    # anchored to several local bodies (across one or more levels) at once.
    lb_ids_by_level = _local_body_ids_by_level(scope)
    any_lb_level, any_lb_ids = next(iter(lb_ids_by_level.items()), (None, None))

    # Backfill missing parents from one of the anchoring local bodies (they
    # all share the same district/area_type, enforced by the Staff Access
    # Configuration form's cascading selection) so the tree can still be
    # rooted at a district even if only the local body was stored.
    if any_lb_level and not (state_id and district_id and area_type_id):
        model, _ = lb_models[any_lb_level]
        row = (
            model.objects.filter(unique_id=any_lb_ids[0])
            .values("state_id", "district_id", "area_type_id")
            .first()
        )
        if row:
            state_id = state_id or row["state_id"]
            district_id = district_id or row["district_id"]
            area_type_id = area_type_id or row["area_type_id"]

    # Districts in scope.
    if district_id:
        district_ids = [district_id]
    elif state_id:
        district_ids = list(
            District.objects.filter(state_id=state_id, is_deleted=False)
            .values_list("unique_id", flat=True)
        )
    else:
        district_ids = []

    if not district_ids:
        return {"districts": []}

    # Area types in scope (all under the districts, or just the granted one).
    area_type_qs = AreaType.objects.filter(
        is_deleted=False, district_id__in=district_ids
    )
    if area_type_id:
        area_type_qs = area_type_qs.filter(unique_id=area_type_id)
    area_types = list(area_type_qs.values("unique_id", "name", "district_id"))

    # Local bodies, grouped by (district, area_type). One query per model.
    lb_rows_by_key = {}
    lb_ids_by_level_seen = {level: [] for level in lb_models}
    for level, (model, name_attr) in lb_models.items():
        if lb_ids_by_level and level not in lb_ids_by_level:
            continue
        qs = model.objects.filter(is_deleted=False, district_id__in=district_ids)
        if area_type_id:
            qs = qs.filter(area_type_id=area_type_id)
        if level in lb_ids_by_level:
            qs = qs.filter(unique_id__in=lb_ids_by_level[level])
        for row in qs.values("unique_id", name_attr, "district_id", "area_type_id"):
            key = (row["district_id"], row["area_type_id"])
            lb_rows_by_key.setdefault(key, []).append(
                {
                    "unique_id": row["unique_id"],
                    "name": row[name_attr],
                    "local_body_type": level,
                }
            )
            lb_ids_by_level_seen[level].append(row["unique_id"])

    # Government staff (sub-admins / supervisors) scoped within each local
    # body. One query per non-empty level; mapped back in Python.
    staff_by_lb = {}
    for level, ids in lb_ids_by_level_seen.items():
        if not ids:
            continue
        m2m_field = next(f for lvl, _, f in STAFF_LOCAL_BODY_M2M_LEVELS if lvl == level)
        rows = (
            StaffDataScope.objects.filter(
                is_active=True,
                is_deleted=False,
                **{f"{m2m_field}__unique_id__in": ids},
            ).values(
                f"{m2m_field}__unique_id",
                "staff_id",
                "staff__employee_name",
                "staff__staff_config_name",
                "staff__governmentusertype_id__name",
            )
        )
        for row in rows:
            staff_by_lb.setdefault(row[f"{m2m_field}__unique_id"], []).append(
                {
                    "staff_unique_id": row["staff_id"],
                    "employee_name": row["staff__employee_name"],
                    "role": row["staff__governmentusertype_id__name"],
                    "staff_config_name": row["staff__staff_config_name"],
                }
            )

    district_names = dict(
        District.objects.filter(unique_id__in=district_ids).values_list(
            "unique_id", "name"
        )
    )

    area_types_by_district = {}
    for area_type in area_types:
        area_types_by_district.setdefault(area_type["district_id"], []).append(area_type)

    districts_payload = []
    for did in district_ids:
        area_type_payload = []
        for area_type in area_types_by_district.get(did, []):
            local_bodies = lb_rows_by_key.get((did, area_type["unique_id"]), [])
            for local_body in local_bodies:
                local_body["staff"] = staff_by_lb.get(local_body["unique_id"], [])
            area_type_payload.append(
                {
                    "unique_id": area_type["unique_id"],
                    "name": area_type["name"],
                    "group": AREA_TYPE_GROUP.get(area_type["name"]),
                    "local_bodies": local_bodies,
                }
            )
        districts_payload.append(
            {
                "unique_id": did,
                "name": district_names.get(did),
                "area_types": area_type_payload,
            }
        )

    return {"districts": districts_payload}


def expanded_scope_payload(user):
    """Public wrapper: the requester's granted level plus the geo subtree
    beneath it, or None when the user is unscoped (super admin / full access).
    Login embeds the same data inside `staff_scope_payload`."""
    scope = _staff_scope(user)
    if not scope:
        return None
    return {
        "granted_level": _granted_scope_level(scope),
        "descendants": _expanded_descendants(scope),
    }


CITY_LEVEL_NAMES = {"Corporation", "Municipality", "Town Panchayat", "Panchayat Union", "Panchayat"}


def district_and_city_for_node(node_id, cache=None):
    """Resolve the District ancestor and the city/local-body ancestor of a node.

    Walks the closure table once (including the self row at depth 0) so a
    node that IS the District (or the city) resolves to itself. Returns
    ``{"district_id", "district_name", "city_id", "city_name"}`` - values are
    None if the node has no such ancestor. Pass a dict as `cache` to reuse
    lookups across many nodes that share the same district/city (e.g. a page
    of tickets) within a single request.
    """
    empty = {"district_id": None, "district_name": None, "city_id": None, "city_name": None}
    if not node_id:
        return empty
    if cache is not None and node_id in cache:
        return cache[node_id]

    links = HierarchyClosure.objects.filter(
        descendant_id=node_id, is_deleted=False
    ).select_related("ancestor", "ancestor__level")

    result = dict(empty)
    for link in links:
        ancestor = link.ancestor
        if not ancestor or ancestor.is_deleted or not ancestor.level_id:
            continue
        level_name = ancestor.level.name
        if level_name == "District":
            result["district_id"] = ancestor.unique_id
            result["district_name"] = ancestor.name
        elif level_name in CITY_LEVEL_NAMES:
            result["city_id"] = ancestor.unique_id
            result["city_name"] = ancestor.name

    if cache is not None:
        cache[node_id] = result
    return result
