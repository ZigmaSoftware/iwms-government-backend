"""
Per-API-scope, per-HTTP-method rate limits used by
app.utils.throttling.MethodScopedRateThrottle (see config/settings.py,
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES']).

Moved out of settings.py because this table is long (one entry per API
view) and purely data — keeping it in its own file keeps settings.py
readable. Each scope name matches a view's `throttle_scope` class
attribute in app/viewsets/**. Edit a rate here to change that one API's
limit; nothing else needs to change.

Rates are tiered instead of one flat number for every endpoint, because
"5/minute for everything" throttled normal usage: an admin paginating,
searching or sorting a masters datagrid (each interaction is its own GET)
or a field app polling its current trip/attendance state trips a limit
meant for a login form in a matter of seconds. Pick the tier that matches
what the endpoint actually is, then override only if that specific API
has an unusual traffic pattern:

  * AUTH_SENSITIVE   — login, OTP, password reset/change, token refresh.
                       Kept tight: these are the classic brute-force /
                       credential-stuffing / OTP-spam targets, and a
                       legitimate user only calls them a handful of
                       times per session.
  * READ_MASTER_DATA — admin CRUD screens over reference/masters data
                       (states, districts, wards, complaint masters,
                       screen/permission masters, user-type masters,
                       ...). GET is generous because one datagrid session
                       fires many of them (pagination, search-as-you-type,
                       column sort, status toggles all re-fetch); writes
                       stay moderate since create/update/delete on
                       reference data is inherently infrequent.
  * DASHBOARD        — summary/aggregation screens that poll or re-render
                       on filter changes; read-heavy like masters data but
                       usually has no meaningful write path.
  * AUDIT_LOG        — read-only audit/log trails, browsed with heavy
                       pagination and filtering by admins investigating
                       an incident; writes are system-generated, not
                       user-initiated, so they don't need real headroom.
  * REALTIME_MOBILE  — operator/field mobile app endpoints (trip
                       lifecycle, bin scanning/QR validation, waste
                       collection bluetooth sessions, attendance
                       check-in/recognition, live daily-operations
                       tracking). These poll frequently by design (GPS
                       pings, scan retries, periodic status refresh) and
                       run on flaky mobile networks where a client retry
                       after a dropped connection must not itself trip
                       the limit.

A scope may still be a single rate string, e.g. "5/minute", instead of a
tier dict — that applies to every HTTP method unchanged from before.

An entry may also be a dict of per-method overrides with a required
"default" fallback, e.g.:
    "customer_creation": {
        "default": "10/minute",
        "GET": "100/minute",
        "POST": "20/minute",
        "PUT": "30/minute",
        "PATCH": "30/minute",
        "DELETE": "10/300s",   # 10 requests per 5 minutes
    }
A method not listed uses "default". A dict without "default" and without
an entry for the current method disables throttling for that method
(matches ScopedRateThrottle's own "no scope -> allow" rule).
"""

# ── Tiers ────────────────────────────────────────────────────────────
# Shared rate dicts, reused by reference below so every scope in a tier
# moves together when the tier's numbers are tuned. Do not mutate a tier
# dict in place from a scope entry — copy it (`{**TIER, "POST": "..."}`)
# if one scope needs a one-off override, so the shared tier is unaffected.

AUTH_SENSITIVE = {
    "default": "5/minute",
    "GET": "5/minute",
    "POST": "5/minute",
    "PUT": "5/minute",
    "PATCH": "5/minute",
    "DELETE": "5/minute",
}

READ_MASTER_DATA = {
    "default": "20/minute",
    "GET": "120/minute",
    "POST": "20/minute",
    "PUT": "20/minute",
    "PATCH": "30/minute",   
    "DELETE": "15/minute",
}

DASHBOARD = {
    "default": "30/minute",
    "GET": "90/minute",
    "POST": "30/minute",
    "PUT": "30/minute",
    "PATCH": "30/minute",
    "DELETE": "15/minute",
}

AUDIT_LOG = {
    "default": "20/minute",
    "GET": "100/minute",
    "POST": "10/minute",
    "PUT": "10/minute",
    "PATCH": "10/minute",
    "DELETE": "10/minute",
}

REALTIME_MOBILE = {
    "default": "60/minute",
    "GET": "120/minute",
    "POST": "60/minute",
    "PUT": "60/minute",
    "PATCH": "60/minute",
    "DELETE": "30/minute",
}

API_THROTTLE_RATES = {
    # ── Auth / sensitive endpoints — tighter limits ────────────────
    "otp": AUTH_SENSITIVE,
    "reset_password": AUTH_SENSITIVE,
    "change_password": AUTH_SENSITIVE,
    "admin_change_password": AUTH_SENSITIVE,
    "platform_login": AUTH_SENSITIVE,
    "refresh_token": AUTH_SENSITIVE,
    "district_leader_login": AUTH_SENSITIVE,
    "panchayat_leader_login": AUTH_SENSITIVE,
    "state_leader_login": AUTH_SENSITIVE,
    "recognize": AUTH_SENSITIVE,
    "register": AUTH_SENSITIVE,

    # ── Dashboards — read-heavy summary/aggregation screens ────────
    "dashboard_summary": DASHBOARD,
    "district_body_dashboard": DASHBOARD,
    "state_body_dashboard": DASHBOARD,
    "local_body_dashboard": DASHBOARD,
    "staff_access_dashboard": DASHBOARD,
    "dashboard_widget_permission": DASHBOARD,

    # ── Audit / log trails — read-heavy, admin investigation use ───
    "audit_log": AUDIT_LOG,
    "staff_audit": AUDIT_LOG,
    "common_audit": AUDIT_LOG,
    "login_audit": AUDIT_LOG,

    # ── Operator/field mobile app — frequent polling by design ─────
    "trip_history": REALTIME_MOBILE,
    "trip_lifecycle": REALTIME_MOBILE,
    "my_trip_today": REALTIME_MOBILE,
    "my_trips_today": REALTIME_MOBILE,
    "scan_bin": REALTIME_MOBILE,
    "validate_bin_qr": REALTIME_MOBILE,
    "waste_collection_bluetooth": REALTIME_MOBILE,
    "waste_collection_main": REALTIME_MOBILE,
    "waste_collection_sub": REALTIME_MOBILE,
    "waste_collection": REALTIME_MOBILE,
    "daily_trip_assignment": REALTIME_MOBILE,
    "daily_trip_collection_point": REALTIME_MOBILE,
    "daily_trip_household_collection": REALTIME_MOBILE,
    "daily_trip_log": REALTIME_MOBILE,
    "bin_collection_event": REALTIME_MOBILE,
    "trip_retrip_request": REALTIME_MOBILE,
    "vehicle_breakdown": REALTIME_MOBILE,
    "daily_attendance_reg": REALTIME_MOBILE,
    "attendance_records": REALTIME_MOBILE,
    "staff_profile": REALTIME_MOBILE,
    "trip_attendance": REALTIME_MOBILE,

    # ── Everything else — CRUD over masters/reference/config data ──
    "administrative_hierarchy": READ_MASTER_DATA,
    "alternative_staff_template": READ_MASTER_DATA,
    "app_module": READ_MASTER_DATA,
    "area_type": READ_MASTER_DATA,
    "bins": READ_MASTER_DATA,
    "block_panchayat_union": READ_MASTER_DATA,
    "captcha": READ_MASTER_DATA,
    "citizen_complaint_ticket": READ_MASTER_DATA,
    "collection_point": READ_MASTER_DATA,
    "company_user_screen_column_permission": READ_MASTER_DATA,
    "complaint_address_change": READ_MASTER_DATA,
    "complaint_category": READ_MASTER_DATA,
    "complaint_feedback": READ_MASTER_DATA,
    "complaint_language": READ_MASTER_DATA,
    "complaint_module": READ_MASTER_DATA,
    "complaint_notification": READ_MASTER_DATA,
    "complaint_priority": READ_MASTER_DATA,
    "complaint_reopen_history": READ_MASTER_DATA,
    "complaint_routing_rule": READ_MASTER_DATA,
    "complaint_sla_rule": READ_MASTER_DATA,
    "complaint_source": READ_MASTER_DATA,
    "complaint_status": READ_MASTER_DATA,
    "complaint_subcategory": READ_MASTER_DATA,
    "complaint_team": READ_MASTER_DATA,
    "complaint_ticket": READ_MASTER_DATA,
    "continent": READ_MASTER_DATA,
    "contractor_user_type": READ_MASTER_DATA,
    "corporation": READ_MASTER_DATA,
    "country": READ_MASTER_DATA,
    "customer_access_configuration": READ_MASTER_DATA,
    "customer_creation": {**READ_MASTER_DATA, "GET": "120/minute"},
    "daily_waste_comparison": READ_MASTER_DATA,
    "department": READ_MASTER_DATA,
    "designation": READ_MASTER_DATA,
    "district": READ_MASTER_DATA,
    "feed_back": READ_MASTER_DATA,
    "fuel": READ_MASTER_DATA,
    "government_staff_user_type": READ_MASTER_DATA,
    "main_screen": READ_MASTER_DATA,
    "main_screen_type": READ_MASTER_DATA,
    "monthly_waste_comparison_report": READ_MASTER_DATA,
    "municipality": READ_MASTER_DATA,
    "panchayat_union": READ_MASTER_DATA,
    "panhayat": READ_MASTER_DATA,
    "permission": READ_MASTER_DATA,
    "permission_assign_api": READ_MASTER_DATA,
    "property": READ_MASTER_DATA,
    "public_grievance": READ_MASTER_DATA,
    "staff": READ_MASTER_DATA,
    "staff_access_configuration": READ_MASTER_DATA,
    "staff_notification": REALTIME_MOBILE,
    "staff_template": READ_MASTER_DATA,
    "staff_user_type": READ_MASTER_DATA,
    "staffcreation": READ_MASTER_DATA,
    "state": READ_MASTER_DATA,
    "state_daily_waste_comparison": READ_MASTER_DATA,
    "state_monthly_waste_comparison": READ_MASTER_DATA,
    "sub_property": READ_MASTER_DATA,
    "town_panchayat": READ_MASTER_DATA,
    "trip_plan": READ_MASTER_DATA,
    "unassigned_staff_pool": READ_MASTER_DATA,
    "user_charge_rule": READ_MASTER_DATA,
    "user_permissions_api": READ_MASTER_DATA,
    "user_screen": READ_MASTER_DATA,
    "user_screen_action": READ_MASTER_DATA,
    "user_screen_columns_api": READ_MASTER_DATA,
    "user_screen_permission": READ_MASTER_DATA,
    "user_type": READ_MASTER_DATA,
    "vehicle_creation": READ_MASTER_DATA,
    "vehicle_type_creation": READ_MASTER_DATA,
    "ward": READ_MASTER_DATA,
    "waste_type": READ_MASTER_DATA,
}
