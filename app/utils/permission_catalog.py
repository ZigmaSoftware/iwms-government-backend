"""The permission catalog: ONE definition of every module and screen.

Modelled on iwms-private's catalog, but keyed to THIS codebase's admin sidebar
(iwms-government-frontend/src/layouts/admin/sidebarMenu.tsx): every sidebar
heading is a module and every sidebar entry is a screen, named after what the
sidebar shows — "Daily Operations" is `daily-operations`, its "Daily Trip
Plan" entry is `daily-trip-plan` — and listed in the same order.

Everything that names a permission reads it from here:

- the permission seeder creates the MainScreen / UserScreen rows
  (seeders/superadmin/screen_management/permissions.py), renames rows still
  carrying a `legacy` name, and retires any screen no longer listed;
- ModulePermissionMiddleware authorizes each URL route listed under a screen's
  `routes` with that screen's grant (ROUTE_OWNERS);
- the frontend sidebar and route guard import the generated copy,
  iwms-government-frontend/src/generated/permissionCatalog.ts
  (`python manage.py sync_permission_catalog`, also run by `seed`), so a wrong
  module/screen name there is a TypeScript error.

After editing this file re-run the permission seeder
(`python manage.py seed --group screen-managements`).

Naming rules
------------
- A module's `name` is the MainScreen name (the permission key): the sidebar
  heading's label in kebab-case. `url_module` is the router group in
  app/urls/base_urls.py its routes live under.
- A screen's `name` is the UserScreen name: the sidebar entry's label in
  kebab-case. Its routes default to "<url_module>/<name>"; give `routes`
  explicitly when the router uses another path (the usual case), when one
  screen covers several routes, or `()` for a page with no protected route of
  its own. A bare route is relative to the module's url_module; "group/route"
  is absolute.
- Every sidebar entry is a screen, even a page with no API of its own (Daily
  Trip Tracking, Apartment List): granting "view" on it is what shows it.
  Whatever it reads belongs in SCREEN_DEPENDENCIES (screen_dependencies.py).
- Grants are stored against the row, not the name, so a rename is safe as
  long as the old name is listed in `legacy`: the seeder renames that row in
  place. `absorbs` names retired screens whose grants are copied onto this
  one (tabs folded into one page); `inherits_grants_from` gives a NEW screen
  the grants of the screen it was split from, so nobody loses access.
"""


def screen(
    name,
    label,
    *,
    routes=None,
    model=None,
    legacy=(),
    absorbs=(),
    inherits_grants_from=None,
):
    return {
        "name": name,
        "label": label,
        "routes": routes,
        "model": model,
        "legacy": tuple(legacy),
        "absorbs": tuple(absorbs),
        "inherits_grants_from": inherits_grants_from,
    }


def module(
    name, label, screens, *, url_module=None, icon=None, description="", legacy=(),
):
    return {
        "name": name,
        "label": label,
        "url_module": url_module or name,
        "icon": icon or name,
        "description": description or label,
        "screens": screens,
        "legacy": tuple(legacy),
    }


# The sidebar's Daily Trip Plan page is backed by three tables. One grant on
# "daily-trip-plan" covers all of them.
DAILY_TRIP_PLAN_TABLES = (
    "daily-trip-assignments",
    "daily-trip-collection-points",
    "daily-trip-household-collections",
)

# Staff / contractor / government user types are tabs of one page.
STAFF_USER_TYPE_TABLES = (
    "staffusertypes",
    "contractorusertypes",
    "governmentusertypes",
)


# (sidebar group, modules) in sidebar order — sidebarMenu.tsx MODULE_GROUPS.
SECTIONS = (
    ("dashboard", (
        module("dashboard", "Dashboard", (
            # Served by the unprotected "dashboard" route group.
            screen("dashboard", "Dashboard", routes=(), legacy=("Dashboard",)),
        ), icon="dashboard", description="Dashboard landing page"),
    )),
    ("super-admin", (
        module("screen-management", "Screen Management", (
            screen(
                "mainscreen-type", "MainScreen Type",
                routes=("mainscreentype",), legacy=("mainscreentype",),
                model=("app", "MainScreenType"),
            ),
            screen(
                "mainscreen", "MainScreen",
                routes=("mainscreens",), legacy=("mainscreens",),
                model=("app", "MainScreen"),
            ),
            screen(
                "user-screen", "User Screen",
                routes=("userscreens",), legacy=("userscreens",),
                model=("app", "UserScreen"),
            ),
            screen(
                "userscreen-action", "UserScreen Action",
                model=("app", "UserScreenAction"),
            ),
            # The permission page also saves column and widget permissions.
            screen(
                "user-screen-permission", "User Screen Permission",
                routes=(
                    "userscreenpermissions",
                    "companywisescreenpermissions",
                    "column-permissions",
                    "dashboard-widget-permissions",
                ),
                legacy=("userscreenpermissions",),
                model=("app", "UserScreenPermission"),
            ),
            screen("app-modules", "App Modules", model=("app", "AppModule")),
        ), url_module="screen-managements", icon="settings",
           description="Screen setup and permission management",
           legacy=("screen-managements",)),
        module("role-management", "Role Management", (
            screen("user-type", "User Type", model=("app", "UserType")),
            screen(
                "staff-user-type", "Staff User Type",
                routes=STAFF_USER_TYPE_TABLES,
                model=("app", "StaffUserType"),
            ),
            screen("staff-hierarchy", "Staff Hierarchy"),
        ), url_module="role-assigns", icon="admin_panel_settings",
           description="Role assignment configuration", legacy=("role-assigns",)),
        module("staff-management", "Staff Management", (
            screen(
                "staff-creation", "Staff Creation",
                routes=("staffcreation", "users-creation"),
                legacy=("staffcreation",),
                model=("app", "StaffcreationOfficeDetails"),
            ),
            screen(
                "staff-access-configuration", "Staff Access Configuration",
                model=("app", "StaffcreationOfficeDetails"),
            ),
            screen(
                "staff-access-dashboard", "Staff Access Dashboard",
                model=("app", "StaffcreationOfficeDetails"),
            ),
        ), url_module="user-creations", icon="group_add",
           description="User and staff creation", legacy=("user-creations",)),
        module("common-masters", "Common Masters", (
            screen(
                "continent", "Continent",
                routes=("continents",), legacy=("continents",),
                model=("app", "Continent"),
            ),
            screen(
                "country", "Country",
                routes=("countries",), legacy=("countries",),
                model=("app", "Country"),
            ),
            screen(
                "state", "State",
                routes=("states",), legacy=("states",),
                model=("app", "State"),
            ),
        ), icon="layers", description="Common geographic master data"),
        # Same screens as iwms-private's audits module (less its static
        # route audit, which has no government counterpart).
        module("audits", "Audits", (
            screen("audit-dashboard", "Audit Dashboard"),
            # Transaction Audit absorbed the old "Collection Audit"
            # (staff-audit) screen; RESOURCE_PERMISSION_ALIASES keeps grants
            # on that retired screen working.
            screen("common-audit", "Common Audit", model=("app", "CommonAudit")),
            screen("login-audit", "Login Audit", model=("app", "LoginAudit")),
            screen(
                "user-access-audit", "User Access Audit",
                routes=("permission-audit",), legacy=("permission-audit",),
                model=("app", "PermissionAuditLog"),
            ),
            screen("complaint-audit", "Complaint Audit"),
        ), icon="fact_check", description="Audit and activity logs"),
    )),
    ("masters", (
        module("location-masters", "Location Masters", (
            screen(
                "district", "District",
                routes=("districts",), legacy=("districts",),
                model=("app", "District"),
            ),
            screen(
                "area-type", "Area Type",
                routes=("areatypes",), legacy=("area-types",),
                model=("app", "AreaType"),
            ),
            screen(
                "corporation", "Corporation",
                routes=("corporations",), legacy=("corporations",),
                model=("app", "Corporation"),
            ),
            screen(
                "municipality", "Municipality",
                routes=("municipalities",), legacy=("municipalities",),
                model=("app", "Municipality"),
            ),
            screen(
                "town-panchayat", "Town Panchayat",
                routes=("town-panchayats",), legacy=("town-panchayats",),
                model=("app", "TownPanchayat"),
            ),
            screen(
                "panchayat-union", "Panchayat Union",
                routes=("panchayat-unions",), legacy=("panchayat-unions",),
                model=("app", "PanchayatUnion"),
            ),
            screen(
                "plb", "PLB (Participating Local Bodies)",
                routes=("panchayat",), legacy=("panchayats",),
                model=("app", "Panchayat"),
            ),
            screen(
                "ward", "Ward",
                routes=("wards",), legacy=("wards",),
                model=("app", "Ward"),
            ),
        ), url_module="masters", icon="layers",
           description="Administrative and local-body master data", legacy=("masters",)),
        module("waste-masters", "Waste Masters", (
            screen(
                "waste-type", "Waste Type",
                routes=("wastetypes",), legacy=("wastetypes",),
                model=("app", "WasteType"),
            ),
            screen(
                "property", "Property",
                routes=("properties",), legacy=("properties",),
                model=("app", "Property"),
            ),
            screen(
                "subproperty", "SubProperty",
                routes=("subproperties",), legacy=("subproperties",),
                model=("app", "SubProperty"),
            ),
            screen(
                "bin-creation", "Bin Creation",
                routes=("bins",), legacy=("bins",),
                model=("app", "Bins"),
            ),
        ), url_module="waste-types", icon="recycling",
           description="Waste type and asset configuration", legacy=("waste-types",)),
        module("transport-masters", "Transport Masters", (
            screen("vehicle-type", "Vehicle Type", model=("app", "VehicleTypeCreation")),
            screen("vehicle-creation", "Vehicle Creation", model=("app", "VehicleCreation")),
            screen(
                "fuel", "Fuel",
                routes=("fuels",), legacy=("fuels",),
                model=("app", "Fuel"),
            ),
        ), icon="local_shipping", description="Transport and vehicle setup"),
        module("customer-masters", "Customer Masters", (
            screen(
                "customer-creation", "Customer Creation",
                routes=("customercreations",), legacy=("customercreations",),
                model=("app", "CustomerCreation"),
            ),
            # Reads the customer list (SCREEN_DEPENDENCIES lookup).
            screen(
                "apartment-list", "Apartment List",
                routes=(), inherits_grants_from="customer-creation",
            ),
            screen("customer-access-configuration", "Customer Access Configuration"),
        ), icon="groups", description="Customer master screens", legacy=("customers",)),
        # The leader logins route under the "masters" group.
        module("leader-management", "Leader Management", (
            screen(
                "plb-leader-creation", "PLB Leader Creation",
                routes=("masters/panchayat-leaders",),
                model=("app", "PanchayatLeaderLogin"),
            ),
            screen(
                "district-leader-creation", "District Leader Creation",
                routes=("masters/district-leaders",),
                model=("app", "DistrictLeaderLogin"),
            ),
            screen(
                "state-leader-creation", "State Leader Creation",
                routes=("masters/state-leaders",),
                model=("app", "StateLeaderLogin"),
            ),
        ), icon="badge", description="Leader login management", legacy=("leader-login",)),
    )),
    ("core-modules", (
        module("schedule-setup", "Schedule Setup", (
            screen(
                "staff-template", "Staff Template",
                routes=("staff-templates",), legacy=("staff-templates",),
                model=("app", "StaffTemplate"),
            ),
            screen(
                "alternative-staff-template", "Alternative Staff Template",
                routes=("alternative-staff-templates",),
                legacy=("alternative-staff-templates",),
                model=("app", "AlternativeStaffTemplate"),
            ),
            screen(
                "collection-point", "Collection Point",
                routes=("collection-points",), legacy=("collection-points",),
                model=("app", "Collection_point"),
            ),
            screen("trip-plans", "Trip Plans", model=("app", "TripPlan")),
        ), icon="event_note", description="Schedule planning and configuration"),
        module("daily-operations", "Daily Operations", (
            # ONE grant for the daily trip plan and its three tables: the trip
            # (assignment), its collection-point stops and its household stops.
            screen(
                "daily-trip-plan", "Daily Trip Plan",
                routes=DAILY_TRIP_PLAN_TABLES,
                legacy=("daily-trip-plans",),
                absorbs=("daily-trip-assignments", "daily-trip-collection-points"),
                model=("app", "DailyTripAssignment"),
            ),
            # Read-only page over the trip stops (SCREEN_DEPENDENCIES lookups);
            # was opened by the daily trip plan grant, hence its grants.
            screen(
                "daily-trip-tracking", "Daily Trip Tracking",
                routes=(), inherits_grants_from="daily-trip-plan",
            ),
            screen(
                "secondary-bin-collection-event", "Secondary Bin Collection Event",
                routes=("bin-collection-events",),
                legacy=("secondary-bin-collection-events",),
                model=("app", "BinCollectionEvent"),
            ),
            screen(
                "household-collection-event", "Household Collection Event",
                routes=("wastecollections",),
                legacy=("householdcollection-events",),
                model=("app", "WasteCollection"),
            ),
            screen(
                "vehicle-breakdown", "Vehicle Breakdown",
                routes=("vehicle-breakdowns",), legacy=("vehicle-breakdowns",),
                model=("app", "VehicleBreakdown"),
            ),
            # retrip-requests / staff-notifications are auth-only routes (see
            # AUTH_ONLY_SUFFIXES); these screens gate the pages and app tabs.
            screen(
                "re-trip-requests", "Re-Trip Requests",
                routes=("retrip-requests",), legacy=("retrip-requests",),
            ),
            screen("daily-trip-logs", "Daily Trip Logs", model=("app", "DailyTripLog")),
            # Mobile app only: no sidebar entry.
            screen("staff-notifications", "Staff Notifications (Mobile App)"),
        ), url_module="schedule-operations", icon="calendar_check",
           description="Daily schedule execution and tracking",
           legacy=("schedule-operations",)),
        module("complaint-management", "Complaint Management", (
            # Feedback, reopen history, notifications and address changes are
            # shown inside the ticket page, so the tickets grant covers them.
            screen(
                "complaint-tickets", "Complaint Tickets",
                routes=(
                    "tickets",
                    "feedback",
                    "reopen-history",
                    "notifications",
                    "address-change",
                ),
                legacy=("tickets",),
                model=("app", "ComplaintTicket"),
            ),
            # A page over the tickets API (SCREEN_DEPENDENCIES includes).
            screen("my-tasks", "My Tasks", routes=()),
            # One page, four tabs: one grant covers them all.
            screen(
                "reference-data", "Reference Data",
                routes=("modules", "priorities", "sources", "statuses"),
                legacy=("modules",),
                absorbs=("priorities", "sources", "statuses"),
                model=("app", "ComplaintModule"),
            ),
            # Master-detail page: categories and their subcategories.
            screen(
                "categories", "Categories",
                routes=("categories", "subcategories"),
                absorbs=("subcategories",),
                model=("app", "ComplaintCategory"),
            ),
            screen("sla-rules", "SLA Rules", model=("app", "ComplaintSlaRule")),
        ), url_module="complaint-ticket", icon="support_agent",
           description="Complaint ticket management", legacy=("complaint-ticket",)),
        module("attendance", "Attendance", (
            # register/recognize/staff-profile/face-config are public or
            # auth-only (see the middleware); only the records list is gated.
            screen(
                "attendance", "Attendance",
                routes=("records",),
                model=("app", "DailyAttendanceReg"),
            ),
        ), icon="calendar_check", description="Staff face-recognition attendance"),
    )),
    ("reports", (
        module("waste-reports", "Waste Reports", (
            screen(
                "daily-waste-comparison", "Daily Waste Comparison",
                routes=("daily-waste-comparisons",),
                legacy=("daily-waste-comparisons",),
                model=("app", "DailyWasteComparison"),
            ),
            screen(
                "monthly-waste-comparison", "Monthly Waste Comparison",
                # The "reports/..." alias routes stay unprotected: the
                # dashboard, which every staff member sees, reads them.
                routes=("monthly-waste-comparison",),
                legacy=("MonthlyWasteComparison",),
                model=("app", "MonthlyWeightReport"),
            ),
        ), url_module="schedule-masters", icon="bar_chart",
           description="Schedule and waste reports", legacy=("schedule-masters",)),
        module("complaint-reports", "Complaint Reports", (
            screen("complaints-report", "Complaints Report"),
        ), url_module="complaint-ticket", icon="bar_chart",
           description="Complaint analytics"),
    )),
)


# ------------------------------------------------------------------
# Derived views — use these rather than walking SECTIONS yourself.
# ------------------------------------------------------------------

MODULES = {m["name"]: m for _, modules in SECTIONS for m in modules}

# {mainscreen: [userscreen, ...]} in sidebar order.
SCREEN_STRUCTURE = {
    name: [s["name"] for s in m["screens"]] for name, m in MODULES.items()
}

SCREENS = {s["name"]: s for m in MODULES.values() for s in m["screens"]}

MAINSCREEN_LABELS = {name: m["label"] for name, m in MODULES.items()}
SCREEN_LABELS = {name: s["label"] for name, s in SCREENS.items()}

# userscreen -> (app_label, model_name) for the schema resolver.
SCREEN_MODELS = {name: s["model"] for name, s in SCREENS.items() if s["model"]}

# Old name -> current name, for rows and grants stored before a rename.
LEGACY_MODULE_NAMES = {
    old: name for name, m in MODULES.items() for old in m["legacy"]
}
LEGACY_SCREEN_NAMES = {
    old: name for name, s in SCREENS.items() for old in (*s["legacy"], *s["absorbs"])
}

# New screen -> screen whose grants it copies when first seeded.
INHERITS_GRANTS_FROM = {
    name: s["inherits_grants_from"]
    for name, s in SCREENS.items()
    if s["inherits_grants_from"]
}


def screen_routes(mod, scr):
    """Full "<url-module>/<route>" keys a screen owns."""
    routes = (scr["name"],) if scr["routes"] is None else scr["routes"]
    return tuple(r if "/" in r else f"{mod['url_module']}/{r}" for r in routes)


def _check_unique_names():
    seen = {}
    for m in MODULES.values():
        for s in m["screens"]:
            for name in (s["name"], *s["legacy"], *s["absorbs"]):
                if name in seen and seen[name] != s["name"]:
                    raise ValueError(
                        f"Screen name {name!r} is claimed by both "
                        f"{seen[name]!r} and {s['name']!r}."
                    )
                seen[name] = s["name"]
    for name, source in INHERITS_GRANTS_FROM.items():
        if source not in SCREENS:
            raise ValueError(f"{name!r} inherits from unknown screen {source!r}.")


def _route_owners():
    owners = {}
    for m in MODULES.values():
        for s in m["screens"]:
            for route in screen_routes(m, s):
                if route in owners:
                    raise ValueError(
                        f"Route {route!r} is owned by both {owners[route]} and "
                        f"{(m['name'], s['name'])}; a route has one owner."
                    )
                owners[route] = (m["name"], s["name"])
    return owners


_check_unique_names()

# "<url-module>/<route>" -> (mainscreen, userscreen) whose grant authorizes it.
ROUTE_OWNERS = _route_owners()

# URL route groups a catalog screen owns a route in.
ROUTE_MODULES = frozenset(route.split("/", 1)[0] for route in ROUTE_OWNERS)
