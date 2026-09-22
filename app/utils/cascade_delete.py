"""
Generic, declarative cascade-soft-delete for BaseMaster subclasses.

Each model that should sweep child rows when it is soft-deleted declares a
CASCADE_SOFT_DELETE class attribute - a tuple of reverse-relation accessor
names (the related_name used on the child FK/M2M, exactly as you'd write
`instance.<related_name>`). The child model's own CASCADE_SOFT_DELETE (if
any) is walked transitively by the same function, so a model only needs to
list its OWN direct children, not its whole descendant tree.

Usage:

    class Continent(BaseMaster):
        CASCADE_SOFT_DELETE = ("countries", "states", "districts")
        ...

Models that are NOT soft-deletable (no is_deleted field, e.g. TripAttendance,
AlternativeStaffTemplate, StaffAudit) must never appear in a
CASCADE_SOFT_DELETE tuple - there is nothing for the cascade to flip, and
those tables are intentionally left untouched (audit/log-shaped tables in
particular are meant to be permanent).

ManyToMany relations (e.g. StaffDataScope.wards, TripPlan.wards) are also
deliberately excluded from this mechanism: soft-deleting the target of an
M2M link doesn't make sense - unlinking is a different, smaller operation
and is out of scope here.

Geo-hierarchy relations (child rows that reference a parent via a plain
`<field>_id` unique_id string rather than a real ForeignKey - Corporation,
State, District, AreaType and friends were all converted this way) have no
real reverse accessor for `getattr`/`_meta.get_field` to find. Those relation
names are declared instead in `STRING_FK_CASCADE_RELATIONS` below and
resolved through that registry as a fallback.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction


def _lazy_model(dotted_path):
    """Import a model lazily by dotted path (avoids import-order issues -
    this module is imported very early, from BaseMaster)."""
    import importlib

    module_path, class_name = dotted_path.rsplit(".", 1)
    return getattr(importlib.import_module(module_path), class_name)


# {(dotted declaring-model path, relation_name): (dotted child-model path, filter_field)}
# Populated for every CASCADE_SOFT_DELETE relation name that used to be a
# real reverse-FK/OneToOne accessor before the child's own field was
# converted from ForeignKey to a plain `<field>_id` CharField holding the
# parent's unique_id. See app/utils/hierarchy.py's geo-hierarchy conversion
# for the full list of converted models.
STRING_FK_CASCADE_RELATIONS = {}


def _register(declaring_path, relation_name, child_path, filter_field):
    STRING_FK_CASCADE_RELATIONS[(declaring_path, relation_name)] = (child_path, filter_field)


# ---------------------------------------------------------------------------
# Continent / Country -> State / District / Country chain
# ---------------------------------------------------------------------------
_CONTINENT = "app.models.superadmin.common_masters.continent.Continent"
_COUNTRY = "app.models.superadmin.common_masters.country.Country"
_STATE = "app.models.superadmin.common_masters.state.State"
_DISTRICT = "app.models.masters.district.District"
_AREA_TYPE = "app.models.masters.areatype.AreaType"
_CORPORATION = "app.models.masters.corporation.Corporation"
_MUNICIPALITY = "app.models.masters.municipality.Municipality"
_TOWN_PANCHAYAT = "app.models.masters.town_panchayat.TownPanchayat"
_PANCHAYAT_UNION = "app.models.masters.panchayat_union.PanchayatUnion"
_PANCHAYAT = "app.models.masters.panchayat.Panchayat"

_register(_CONTINENT, "countries", _COUNTRY, "continent_id")
_register(_CONTINENT, "states", _STATE, "continent_id")
_register(_CONTINENT, "districts", _DISTRICT, "continent_id")

_register(_COUNTRY, "states", _STATE, "country_id")
_register(_COUNTRY, "districts", _DISTRICT, "country_id")

# ---------------------------------------------------------------------------
# The 8 geo-hierarchy parent models (State, District, AreaType, Corporation,
# Municipality, TownPanchayat, PanchayatUnion, Panchayat) each cascade to the
# same broad set of consumer tables, keyed by their own `<field>_id` column.
# `wards` and `customer_creations` already have working `@property`
# accessors on these models (see ward.py/customercreation.py's conversion)
# and are intentionally NOT registered here.
# ---------------------------------------------------------------------------
_PARENT_MODELS = (_STATE, _DISTRICT, _AREA_TYPE, _CORPORATION, _MUNICIPALITY, _TOWN_PANCHAYAT, _PANCHAYAT_UNION, _PANCHAYAT)
_PARENT_FIELD = {
    _STATE: "state_id",
    _DISTRICT: "district_id",
    _AREA_TYPE: "area_type_id",
    _CORPORATION: "corporation_id",
    _MUNICIPALITY: "municipality_id",
    _TOWN_PANCHAYAT: "town_panchayat_id",
    _PANCHAYAT_UNION: "panchayat_union_id",
    _PANCHAYAT: "panchayat_id",
}

# Consumer tables that carry the full flat-geo block (state/district/
# area_type/corporation/.../panchayat), all now plain `<field>_id` CharFields.
_FLAT_GEO_CONSUMERS = (
    ("bins", "app.models.masters.waste_masters.bins.Bins"),
    ("vehicles", "app.models.masters.transport_masters.vehicleCreation.VehicleCreation"),
    ("staff_templates", "app.models.core_modules.schedule_setup.staff_template.StaffTemplate"),
    ("collection_points", "app.models.core_modules.schedule_setup.collection_point.Collection_point"),
    ("trip_plans", "app.models.core_modules.schedule_setup.trip_plan.TripPlan"),
    ("trip_plan_collection_points", "app.models.core_modules.schedule_setup.trip_plan_collection_point.TripPlanCollectionPoint"),
    ("daily_trip_logs", "app.models.core_modules.daily_operations.daily_trip_log.DailyTripLog"),
    ("daily_trip_collection_points", "app.models.core_modules.daily_operations.daily_trip_collection_point.DailyTripCollectionPoint"),
    ("daily_trip_assignments", "app.models.core_modules.daily_operations.daily_trip_assignment.DailyTripAssignment"),
    ("daily_trip_household_collections", "app.models.core_modules.daily_operations.daily_trip_household_collection.DailyTripHouseholdCollection"),
    ("vehicle_breakdowns", "app.models.core_modules.daily_operations.vehicle_breakdown.VehicleBreakdown"),
    ("secondary_bin_collection_events", "app.models.core_modules.daily_operations.secondary_bin_collection_event.BinCollectionEvent"),
    ("waste_collections", "app.models.core_modules.daily_operations.waste_collection.WasteCollection"),
    ("complaint_tickets", "app.models.core_modules.complaint_management.ticket.ComplaintTicket"),
    ("staff_members", "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails"),
)

for _parent in _PARENT_MODELS:
    _field = _PARENT_FIELD[_parent]
    for _rel_name, _child_path in _FLAT_GEO_CONSUMERS:
        _register(_parent, _rel_name, _child_path, _field)

# complaint_routing_rules / address_change_requests: not present on AreaType
# (ComplaintRoutingRule has no area_type_id field at all).
_COMPLAINT_ROUTING_RULE = "app.models.core_modules.complaint_management.routing_rule.ComplaintRoutingRule"
_ADDRESS_CHANGE_REQUEST = "app.models.core_modules.complaint_management.address_change_request.ComplaintAddressChangeRequest"
for _parent in (_STATE, _DISTRICT, _CORPORATION, _MUNICIPALITY, _TOWN_PANCHAYAT, _PANCHAYAT_UNION, _PANCHAYAT):
    _register(_parent, "complaint_routing_rules", _COMPLAINT_ROUTING_RULE, _PARENT_FIELD[_parent])
for _parent in _PARENT_MODELS:
    # ComplaintAddressChangeRequest's geo fields are prefixed `new_<field>_id`.
    _register(_parent, "address_change_requests", _ADDRESS_CHANGE_REQUEST, f"new_{_PARENT_FIELD[_parent]}")

# Intra-hierarchy parent/child links (State -> District -> AreaType/Corporation/...).
_register(_STATE, "districts", _DISTRICT, "state_id")
_register(_STATE, "area_type", _AREA_TYPE, "state_id")
_register(_DISTRICT, "area_type", _AREA_TYPE, "district_id")
for _parent in (_STATE, _DISTRICT, _AREA_TYPE):
    _field = _PARENT_FIELD[_parent]
    _register(_parent, "corporations", _CORPORATION, _field)
    _register(_parent, "municipalities", _MUNICIPALITY, _field)
    _register(_parent, "town_panchayats", _TOWN_PANCHAYAT, _field)
    _register(_parent, "panchayat_unions", _PANCHAYAT_UNION, _field)
# District/State use singular "panchayat"; AreaType uses plural "panchayats".
_register(_STATE, "panchayat", _PANCHAYAT, "state_id")
_register(_DISTRICT, "panchayat", _PANCHAYAT, "district_id")
_register(_AREA_TYPE, "panchayats", _PANCHAYAT, "area_type_id")

# leader_logins: declared on Panchayat/District/State only, each pointing at
# its own dedicated leader-login model.
_register(_PANCHAYAT, "leader_logins", "app.models.masters.leader_management.panchayat_leader_login.PanchayatLeaderLogin", "panchayat_id")
_register(_DISTRICT, "leader_logins", "app.models.masters.leader_management.district_leader_login.DistrictLeaderLogin", "district_id")
_register(_STATE, "leader_logins", "app.models.masters.leader_management.state_leader_login.StateLeaderLogin", "state_id")

# scoped_staff / screen-permission scoping: declared on District/AreaType/State only.
_STAFF_DATA_SCOPE = "app.models.superadmin.staff_management.staff_data_scope.StaffDataScope"
_USER_SCREEN_PERMISSION = "app.models.superadmin.screen_management.userscreenpermission.UserScreenPermission"
_COLUMN_PERMISSION = "app.models.superadmin.screen_management.userscreencolumnpermission.UserScreenColumnPermission"
_DASHBOARD_WIDGET_PERMISSION = "app.models.superadmin.screen_management.dashboardwidgetpermission.DashboardWidgetPermission"
for _parent, _scope_field in ((_STATE, "state"), (_DISTRICT, "district"), (_AREA_TYPE, "area_type")):
    _register(_parent, "scoped_staff", _STAFF_DATA_SCOPE, _scope_field)
    _field = _PARENT_FIELD[_parent]
    _register(_parent, "userscreen_column_permissions", _COLUMN_PERMISSION, _field)
    _register(_parent, "dashboard_widget_permissions", _DASHBOARD_WIDGET_PERMISSION, _field)
    _register(_parent, "userscreenpermissions", _USER_SCREEN_PERMISSION, _field)

# users_district: District only.
_register(_DISTRICT, "users_district", "app.models.superadmin_masters.auth_user.User", "district_id")

# departments: Corporation only.
_register(_CORPORATION, "departments", "app.models.masters.department.Department", "corporation_id")


def _resolve_related_manager(model, obj, rel_name):
    """Return an object with `.all()` (an iterable of children) for
    `obj.<rel_name>`, whether that's a real Django reverse-FK/M2M/OneToOne
    accessor or a registered string-FK cascade relation. Returns None if
    neither resolves."""
    try:
        related = getattr(obj, rel_name, None)
    except ObjectDoesNotExist:
        # Reverse OneToOne accessor raises when no related row exists.
        return None
    if related is not None:
        return related

    entry = STRING_FK_CASCADE_RELATIONS.get((_model_path(model), rel_name))
    if entry is None:
        return None
    child_path, filter_field = entry
    child_model = _lazy_model(child_path)
    return child_model.objects.filter(**{filter_field: obj.unique_id})


def _model_path(model):
    return f"{model.__module__}.{model.__qualname__}"


def cascade_soft_delete(instance, updated_by=None):
    """
    Soft-delete `instance` and, transitively, every row reachable via the
    reverse relations named in `type(instance).CASCADE_SOFT_DELETE` (and in
    turn those descendants' own CASCADE_SOFT_DELETE), each exactly once.

    - Deduplicates by (model, pk) so a row reachable by more than one path
      (e.g. a State reachable both via Continent.states directly and via
      Continent -> Country -> State) is only ever updated once.
    - Performs one bulk `.filter(pk__in=[...]).update(is_deleted=True,
      is_active=False, ...)` per model collected, instead of per-instance
      .save()/.delete() calls, for efficiency at scale.
    - When `updated_by` (an Account instance) is given, it is stamped onto
      every row's `updated_by` field in the same bulk update, on every
      model that declares that field - so cascaded rows record who
      triggered the delete, not just the top-level instance.
    - Wrapped in a single transaction.atomic() so a partial cascade can
      never be left half-applied.

    Bulk `.update()` does not invoke each row's `delete()`/`save()` override
    or fire Django signals. This is safe today because every affected
    model's delete() (where overridden) is a trivial is_deleted/is_active
    flip with no other side effects (verified across the codebase). Any
    model added to a CASCADE_SOFT_DELETE tuple in future must keep its
    delete-time side effects (if it ever needs any) out of delete() itself
    (e.g. in a pre_save signal keyed off an is_deleted transition) rather
    than relying on delete() being called per-instance, since this cascade
    bypasses it.
    """
    visited: dict[type, set] = {}

    def _walk(obj):
        model = type(obj)
        pks = visited.setdefault(model, set())
        if obj.pk in pks:
            return
        pks.add(obj.pk)

        for rel_name in getattr(model, "CASCADE_SOFT_DELETE", ()):
            related = _resolve_related_manager(model, obj, rel_name)
            if related is None:
                continue
            if hasattr(related, "all"):
                # Reverse FK / M2M manager, or our registry QuerySet.
                for child in related.all().iterator():
                    _walk(child)
            else:
                # Reverse OneToOne accessor — a single model instance.
                _walk(related)

    _walk(instance)

    with transaction.atomic():
        for model, pks in visited.items():
            update_fields = {"is_deleted": True, "is_active": False}
            if updated_by is not None:
                try:
                    model._meta.get_field("updated_by")
                    update_fields["updated_by"] = updated_by
                except Exception:
                    pass
            model.objects.filter(pk__in=pks, is_deleted=False).update(**update_fields)


def collect_cascade_cache_scopes(instance):
    """
    Returns the de-duplicated union of CACHE_SCOPES declared on `instance`'s
    model and every model reachable through its CASCADE_SOFT_DELETE chain
    (regardless of whether any rows of that model actually existed to
    delete - cheap to over-invalidate a cache scope, expensive to under
    invalidate one). Call this BEFORE cascade_soft_delete() mutates rows if
    you need scopes for models that end up with zero matching rows too;
    walking model classes (not instances) means it works even with no data.
    """
    scopes: set[str] = set()
    seen_models: set[type] = set()

    def _walk_model(model):
        if model in seen_models:
            return
        seen_models.add(model)
        scopes.update(getattr(model, "CACHE_SCOPES", ()))
        for rel_name in getattr(model, "CASCADE_SOFT_DELETE", ()):
            child = _resolve_child_model(model, rel_name)
            if child is not None:
                _walk_model(child)

    def _resolve_child_model(model, rel_name):
        try:
            rel = model._meta.get_field(rel_name)
        except Exception:
            rel = None
        related_model = getattr(rel, "related_model", None) if rel else None
        if related_model is not None:
            return related_model
        entry = STRING_FK_CASCADE_RELATIONS.get((_model_path(model), rel_name))
        if entry is None:
            return None
        return _lazy_model(entry[0])

    _walk_model(type(instance))
    return tuple(scopes)
