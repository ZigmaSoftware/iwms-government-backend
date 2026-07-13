from app.models.masters.hierarchy_tree import HierarchyClosure, HierarchyNode
from app.models.user_creations.staff_data_scope import StaffDataScope

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
        .prefetch_related("location_nodes")
        .select_related(
            "state",
            "district",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",
            "depot",
        )
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
    if scope.depot_id:
        direct_ids.append(scope.depot_id)
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
        return queryset
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


def filter_flat_geo_queryset_by_requester_scope(queryset, user, field_map=None):
    """
    Auto-scope a queryset whose model carries its own flat geo FKs (e.g.
    Corporation/Municipality/.../Panchayat, or any model with matching
    state_id/district_id/.../panchayat_id columns) to the requester's
    `StaffDataScope`. The most specific scope level the staff has set wins:
    a staff scoped to a single Panchayat only sees that Panchayat's rows,
    while one scoped to a District sees every local body within it.

    `field_map` lets a model whose columns don't match `STAFF_GEO_LEVEL_FIELDS`
    verbatim supply its own {scope_field: queryset_field} pairs, most specific
    first. Users with no resolvable scope (e.g. super admins) see everything.
    """
    scope = _staff_scope(user)
    if not scope:
        return queryset

    fields = field_map or {f: f for f in STAFF_GEO_LEVEL_FIELDS}
    for scope_field, queryset_field in fields.items():
        try:
            attname = scope._meta.get_field(scope_field).attname
        except Exception:
            attname = scope_field
        value = getattr(scope, attname, None)
        if value:
            return queryset.filter(**{queryset_field: value})

    return queryset


LOCAL_BODY_TYPE_FIELDS = (
    ("corporation", "corporation_id"),
    ("municipality", "municipality_id"),
    ("town_panchayat", "town_panchayat_id"),
    ("panchayat_union", "panchayat_union_id"),
    ("panchayat", "panchayat_id"),
)


def local_body_scope_for_staff(user):
    """
    Derive the requester's effective Local Body ownership key
    (local_body_type, local_body_id) plus state/district/area_type, from
    their `StaffDataScope` row. Mirrors the most-specific-populated-field
    derivation already used for `localBodyLevel`/`localBodyId` in
    `staff_access_configuration_serializer._data_scope_payload`.

    Returns None if the requester has no resolvable data scope.
    """
    scope = _staff_scope(user)
    if not scope:
        return None

    local_body_type = None
    local_body_id = None
    for level, field in LOCAL_BODY_TYPE_FIELDS:
        value = getattr(scope, field, None)
        if value:
            local_body_type = level
            local_body_id = value
            break

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

    return {
        "state": _ref(scope.state, "name"),
        "district": _ref(scope.district, "name"),
        "area_type": _ref(scope.area_type, "name"),
        "corporation": _ref(scope.corporation, "corporation_name"),
        "municipality": _ref(scope.municipality, "municipality_name"),
        "town_panchayat": _ref(scope.town_panchayat, "town_panchayat_name"),
        "panchayat_union": _ref(scope.panchayat_union, "panchayat_union_name"),
        "panchayat": _ref(scope.panchayat, "panchayat_name"),
        "depot": _ref(scope.depot, "name"),
        "location_nodes": [
            {"unique_id": node.unique_id, "name": node.name}
            for node in scope.location_nodes.all()
        ],
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
