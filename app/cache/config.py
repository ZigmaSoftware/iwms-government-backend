"""
Per-API cache configuration: whether an API's response caching is
enabled, and its TTL in seconds.

Deliberately separate from config/throttle_rates.py — caching and rate
limiting are unrelated concerns with unrelated knobs (see
app/utils/throttling.py's docstring for the rate-limit side). Do not
reuse this table for throttle rates or vice versa.

Each key is a "cache scope": a short name a view opts into explicitly
(see app/cache/decorators.py's @cache_api). A scope absent from this
table is treated as {"enabled": False} — caching is opt-in per API, not
automatic.

To change an API's TTL or turn its caching off, edit only this file —
no ViewSet/APIView code needs to change.
"""

CACHE_CONFIG = {
    # Started as a pilot on the State master API (see
    # app/viewsets/superadmin/common_masters/state_viewset.py) and since
    # extended to most master/reference-data viewsets. Deliberately NOT
    # applied to: audit logs, daily-operations/attendance modules,
    # permission/access-control endpoints (PermissionViewSet,
    # UserScreenPermission, DashboardWidgetPermission,
    # StaffAccessConfiguration, AppModule — staleness there is a security
    # concern, and several already use their own ad hoc cache.clear()),
    # login/OTP/password endpoints, notifications, live/real-time
    # operational data (trip lifecycle, bin scanning, waste-collection
    # bluetooth sessions, unassigned staff pool), and approval-workflow
    # viewsets with complex custom write paths (schedule_setup's
    # CollectionPoint/TripPlan/StaffTemplate/AlternativeStaffTemplate,
    # StaffcreationViewset) — left for a dedicated, more careful pass.
    "state_list": {"enabled": True, "ttl": 600},
    "state_detail": {"enabled": True, "ttl": 300},
    "continent_list": {"enabled": True, "ttl": 600},
    "continent_detail": {"enabled": True, "ttl": 300},
    "country_list": {"enabled": True, "ttl": 600},
    "country_detail": {"enabled": True, "ttl": 300},
    "contractor_user_type_list": {"enabled": True, "ttl": 600},
    "contractor_user_type_detail": {"enabled": True, "ttl": 300},
    "government_staff_user_type_list": {"enabled": True, "ttl": 600},
    "government_staff_user_type_detail": {"enabled": True, "ttl": 300},
    "staff_user_type_list": {"enabled": True, "ttl": 600},
    "staff_user_type_detail": {"enabled": True, "ttl": 300},
    "user_type_list": {"enabled": True, "ttl": 600},
    "user_type_detail": {"enabled": True, "ttl": 300},

    # Extended to masters/reference endpoints (see individual ViewSets
    # under app/viewsets/masters/ for the @cache_api usage).
    "area_type_list": {"enabled": True, "ttl": 600},
    "area_type_detail": {"enabled": True, "ttl": 300},
    "corporation_list": {"enabled": True, "ttl": 600},
    "corporation_detail": {"enabled": True, "ttl": 300},
    "district_list": {"enabled": True, "ttl": 600},
    "district_detail": {"enabled": True, "ttl": 300},
    "municipality_list": {"enabled": True, "ttl": 600},
    "municipality_detail": {"enabled": True, "ttl": 300},
    "panchayat_union_list": {"enabled": True, "ttl": 600},
    "panchayat_union_detail": {"enabled": True, "ttl": 300},
    "panhayat_list": {"enabled": True, "ttl": 600},
    "panhayat_detail": {"enabled": True, "ttl": 300},
    "town_panchayat_list": {"enabled": True, "ttl": 600},
    "town_panchayat_detail": {"enabled": True, "ttl": 300},
    "ward_list": {"enabled": True, "ttl": 600},
    "ward_detail": {"enabled": True, "ttl": 300},
    "department_list": {"enabled": True, "ttl": 600},
    "department_detail": {"enabled": True, "ttl": 300},
    "designation_list": {"enabled": True, "ttl": 600},
    "designation_detail": {"enabled": True, "ttl": 300},
    "block_panchayat_union_list": {"enabled": True, "ttl": 600},
    "block_panchayat_union_detail": {"enabled": True, "ttl": 300},
    "administrative_hierarchy_list": {"enabled": True, "ttl": 600},
    "administrative_hierarchy_detail": {"enabled": True, "ttl": 300},
    "fuel_list": {"enabled": True, "ttl": 600},
    "fuel_detail": {"enabled": True, "ttl": 300},
    "vehicle_type_creation_list": {"enabled": True, "ttl": 600},
    "vehicle_type_creation_detail": {"enabled": True, "ttl": 300},
    "property_list": {"enabled": True, "ttl": 600},
    "property_detail": {"enabled": True, "ttl": 300},
    "waste_type_list": {"enabled": True, "ttl": 600},
    "waste_type_detail": {"enabled": True, "ttl": 300},
    "sub_property_list": {"enabled": True, "ttl": 600},
    "sub_property_detail": {"enabled": True, "ttl": 300},
    "user_charge_rule_list": {"enabled": True, "ttl": 600},
    "user_charge_rule_detail": {"enabled": True, "ttl": 300},

    # Complaint management masters (see app/viewsets/core_modules/complaint_management/).
    "complaint_source_list": {"enabled": True, "ttl": 600},
    "complaint_source_detail": {"enabled": True, "ttl": 300},
    "complaint_language_list": {"enabled": True, "ttl": 600},
    "complaint_language_detail": {"enabled": True, "ttl": 300},
    "complaint_priority_list": {"enabled": True, "ttl": 600},
    "complaint_priority_detail": {"enabled": True, "ttl": 300},
    "complaint_status_list": {"enabled": True, "ttl": 600},
    "complaint_status_detail": {"enabled": True, "ttl": 300},
    "complaint_module_list": {"enabled": True, "ttl": 600},
    "complaint_module_detail": {"enabled": True, "ttl": 300},
    "complaint_team_list": {"enabled": True, "ttl": 300},
    "complaint_team_detail": {"enabled": True, "ttl": 180},
    "complaint_category_list": {"enabled": True, "ttl": 300},
    "complaint_category_detail": {"enabled": True, "ttl": 180},
    "complaint_subcategory_list": {"enabled": True, "ttl": 300},
    "complaint_subcategory_detail": {"enabled": True, "ttl": 180},
    "complaint_sla_rule_list": {"enabled": True, "ttl": 300},
    "complaint_sla_rule_detail": {"enabled": True, "ttl": 180},
    "complaint_routing_rule_list": {"enabled": True, "ttl": 300},
    "complaint_routing_rule_detail": {"enabled": True, "ttl": 180},

    # Screen management (superadmin) — reference/structure data.
    "main_screen_list": {"enabled": True, "ttl": 600},
    "main_screen_detail": {"enabled": True, "ttl": 300},
    "main_screen_type_list": {"enabled": True, "ttl": 600},
    "main_screen_type_detail": {"enabled": True, "ttl": 300},
    "user_screen_list": {"enabled": True, "ttl": 600},
    "user_screen_detail": {"enabled": True, "ttl": 300},
    "user_screen_action_list": {"enabled": True, "ttl": 600},
    "user_screen_action_detail": {"enabled": True, "ttl": 300},

    # Staff/asset masters (simple CRUD, no approval workflow).
    "staff_list": {"enabled": True, "ttl": 300},
    "staff_detail": {"enabled": True, "ttl": 180},
    "bins_list": {"enabled": True, "ttl": 300},
    "bins_detail": {"enabled": True, "ttl": 180},
    "vehicle_creation_list": {"enabled": True, "ttl": 300},
    "vehicle_creation_detail": {"enabled": True, "ttl": 180},

    # Schedule setup (core_modules) — approval-workflow viewsets. Every
    # write path (including custom create/update/destroy overrides) has
    # invalidate_on_commit wired in, so these TTLs are a safety net, not
    # the primary freshness mechanism. Short tier given active
    # status/approval_status churn during normal dispatch operations.
    # See app/viewsets/core_modules/schedule_setup/ for the *_CACHE_SCOPES
    # cross-invalidation between trip_plan/staff_template/
    # alternative_staff_template/collection_point.
    "collection_point_list": {"enabled": True, "ttl": 300},
    "collection_point_detail": {"enabled": True, "ttl": 180},
    "trip_plan_list": {"enabled": True, "ttl": 90},
    "trip_plan_detail": {"enabled": True, "ttl": 60},
    "staff_template_list": {"enabled": True, "ttl": 90},
    "staff_template_detail": {"enabled": True, "ttl": 60},
    "alternative_staff_template_list": {"enabled": True, "ttl": 60},
    "alternative_staff_template_detail": {"enabled": True, "ttl": 60},
}


def get_cache_settings(scope):
    """Return {"enabled": bool, "ttl": int} for a scope, disabled by default."""
    return CACHE_CONFIG.get(scope, {"enabled": False, "ttl": 0})
