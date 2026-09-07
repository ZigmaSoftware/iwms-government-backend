"""Mobile app modules, and what each mobile screen needs to be visible.

Ported from the private backend and re-mapped onto this codebase's screen
catalog. There is ONE permission list: a screen ticked for a role (or on a
StaffAccessConfiguration) grants it in web and in the mobile app identically —
the middleware authorizes both from the same rows, so an admin never has to
reason about two parallel namespaces.

Two things sit alongside that single list:

* **App modules** decide which app a person may sign into at all. They are a
  master (`AppModule`) ticked on the access configuration, not a screen
  permission, because "may open the Driver app" is not an API call.

* **Screen visibility** is a code-owned map from each mobile screen to the ONE
  permission that governs whether it appears. A mobile screen usually reads
  several endpoints, but gating on all of them would mean a missed tick makes a
  tab silently vanish, so only its main list permission decides. Anything else
  it cannot read is hidden inside the screen instead.

Citizens are the one exception: every citizen route is middleware-exempt and
hard-scoped to the logged-in customer, so there is nothing in the permission
catalog to grant them. Their three app screens are ticked on a
CustomerAccessConfiguration and gate the app's UI only.

NAMING: the screen names below are THIS codebase's seeded names, which are not
always the same as the URL segment the route uses (e.g. the screen
`householdcollection-events` fronts the route
`schedule-operations/daily-trip-household-collections`). Those pairs are
reconciled by RESOURCE_PERMISSION_ALIASES in the middleware rather than by
renaming anything here — see tests/test_app_feature_grants.py, which fails if
a name used here cannot actually authorize its route.
"""

# ============================================================
# APP MODULES
# ============================================================

APP_MODULE_SEED = [
    {
        "module_key": "app-citizen",
        "surface_key": "citizen",
        "label": "Customer",
        "route": "/citizen/home",
        "order_no": 1,
        "description": "Citizen app — complaints, collection history, profile.",
    },
    {
        "module_key": "app-driver",
        "surface_key": "driver",
        "label": "Driver",
        "route": "/driver/home",
        "order_no": 2,
        "description": "Driver (Captain) app — trips, households, bins, breakdowns.",
    },
    {
        "module_key": "app-operator",
        "surface_key": "operator",
        "label": "Operator",
        "route": "/operator/home",
        "order_no": 3,
        "description": "Operator app — trips, bins, attendance.",
    },
    {
        "module_key": "app-supervisor",
        "surface_key": "supervisor",
        "label": "Supervisor",
        "route": "/supervisor/home",
        "order_no": 4,
        "description": "Supervisor app — trips, crew, complaints, breakdowns.",
    },
]

APP_MODULE_KEYS = tuple(entry["module_key"] for entry in APP_MODULE_SEED)
APP_SURFACE_KEYS = tuple(entry["surface_key"] for entry in APP_MODULE_SEED)

APP_MODULE_CHOICES = tuple(
    (entry["surface_key"], entry["label"]) for entry in APP_MODULE_SEED
) + (("none", "No App Access"),)

APP_SURFACE_CONFIG = {
    entry["surface_key"]: {"label": entry["label"], "route": entry["route"]}
    for entry in APP_MODULE_SEED
}


# ============================================================
# CITIZEN APP SCREENS
# ============================================================

CITIZEN_APP_MAINSCREEN = "app-citizen"

CITIZEN_APP_SCREENS = [
    "app-citizen-complaints",
    "app-citizen-collections",
    "app-citizen-profile",
]


# ============================================================
# SCREENS THIS PORT ADDS TO THE CATALOG
# ============================================================
# Routes that already exist under schedule-operations but had no seeded
# UserScreen, so no admin could ever grant them. The mobile app calls all
# three. Seeded by the permission seeder; also added to the middleware's
# schedule-operations allowlist, which was likewise missing them.

ADDED_SCHEDULE_OPERATION_SCREENS = [
    "wastecollections",
    "retrip-requests",
    "staff-notifications",
]


# ============================================================
# SCREEN VISIBILITY
# ============================================================
# mobile screen key -> the single (module, screen, action) that makes it
# appear. `None` means always available: the screen either runs entirely on
# middleware-exempt routes (attendance, the operator-mobile scan flow) or is
# the user's own profile, which nobody should be locked out of.
#
# Names match lib/core/permissions/app_screens.dart in the Flutter app.

SCREEN_PERMISSIONS = {
    # ---- Supervisor ----
    "supervisor.dashboard": ("schedule-operations", "daily-trip-assignments", "view"),
    "supervisor.trips": ("schedule-operations", "daily-trip-assignments", "view"),
    "supervisor.crew": ("schedule-setup", "staff-templates", "view"),
    "supervisor.households": ("customers", "customercreations", "view"),
    "supervisor.waste": ("schedule-operations", "wastecollections", "view"),
    "supervisor.breakdowns": ("schedule-operations", "vehicle-breakdowns", "view"),
    "supervisor.retrips": ("schedule-operations", "retrip-requests", "view"),
    "supervisor.complaints": ("complaint-ticket", "tickets", "view"),
    "supervisor.notifications": ("schedule-operations", "staff-notifications", "view"),
    "supervisor.livemap": ("schedule-operations", "daily-trip-collection-points", "view"),
    "supervisor.vehicles": ("transport-masters", "vehicle-creation", "view"),
    # This codebase registers no attendance route group, so there is nothing
    # to authorize against — the tab is always available, exactly as it was
    # before this port. Gate it here only once such a route exists.
    "supervisor.attendance": None,
    "supervisor.profile": None,

    # ---- Driver ----
    "driver.trips": ("schedule-operations", "daily-trip-assignments", "view"),
    # This codebase's screen for the household-collection route.
    "driver.households": ("schedule-operations", "householdcollection-events", "view"),
    "driver.bins": ("schedule-operations", "secondary-bin-collection-events", "view"),
    "driver.breakdowns": ("schedule-operations", "vehicle-breakdowns", "view"),
    "driver.retrips": ("schedule-operations", "retrip-requests", "view"),
    "driver.notifications": ("schedule-operations", "staff-notifications", "view"),
    "driver.customers": ("customers", "customercreations", "view"),
    "driver.attendance": None,
    "driver.profile": None,

    # ---- Operator ----
    "operator.trips": ("schedule-operations", "daily-trip-assignments", "view"),
    "operator.households": ("schedule-operations", "householdcollection-events", "view"),
    "operator.bins": ("schedule-operations", "secondary-bin-collection-events", "view"),
    "operator.breakdowns": ("schedule-operations", "vehicle-breakdowns", "view"),
    "operator.notifications": ("schedule-operations", "staff-notifications", "view"),
    "operator.attendance": None,
    "operator.profile": None,

    # ---- Citizen ----
    # Ticked per customer on a CustomerAccessConfiguration instead; these carry
    # no module permission because the citizen routes need none.
    "citizen.complaints": None,
    "citizen.collections": None,
    "citizen.profile": None,
}


def visible_screens(permissions, surface, citizen_screens=None):
    """Which screens of `surface` the user can see, given their permissions.

    Returns the screen keys the app should render. A screen whose governing
    permission is absent is left out; a screen with no governing permission is
    always included.
    """
    from app.middleware.module_permission_middleware import MODULE_PERMISSION_ALIASES

    prefix = f"{surface}."
    granted = []

    for screen_key, requirement in SCREEN_PERMISSIONS.items():
        if not screen_key.startswith(prefix):
            continue

        if requirement is None:
            if surface == "citizen" and citizen_screens is not None:
                # Citizen screens are ticked explicitly, so an empty selection
                # means nothing is shown rather than everything.
                name = f"app-citizen-{screen_key.split('.', 1)[1]}"
                if name not in citizen_screens:
                    continue
            granted.append(screen_key)
            continue

        module, screen, action = requirement
        actions = (permissions or {}).get(module, {}).get(screen)
        if actions is None:
            alias = MODULE_PERMISSION_ALIASES.get(module)
            if alias:
                actions = (permissions or {}).get(alias, {}).get(screen)
        if actions and action in actions:
            granted.append(screen_key)

    return granted


# ============================================================
# ROLE SCREEN TEMPLATES
# ============================================================
# The screens each app role actually calls. NOT a runtime baseline — nothing is
# granted implicitly. These back the "Apply defaults" button on the access
# configuration form and `manage.py backfill_app_access`, so an admin does not
# have to know which screens the Driver app happens to read.

ROLE_SCREEN_TEMPLATES = {
    "driver": {
        "customers": {"customercreations": ["view"]},
        "schedule-operations": {
            "daily-trip-assignments": ["view", "edit"],
            "daily-trip-collection-points": ["view", "edit"],
            "householdcollection-events": ["view", "edit"],
            "secondary-bin-collection-events": ["view", "add"],
            "daily-trip-logs": ["view", "add", "edit"],
            "vehicle-breakdowns": ["view", "add"],
            "staff-notifications": ["view", "add", "edit"],
            "retrip-requests": ["view"],
        },
        "schedule-setup": {"collection-points": ["view"]},
        "transport-masters": {"vehicle-creation": ["view"], "vehicle-type": ["view"]},
    },
    "operator": {
        "customers": {"customercreations": ["view"]},
        "schedule-operations": {
            "daily-trip-assignments": ["view", "edit"],
            "daily-trip-collection-points": ["view", "edit"],
            "householdcollection-events": ["view", "edit"],
            "secondary-bin-collection-events": ["view", "add"],
            "daily-trip-logs": ["view", "add", "edit"],
            "vehicle-breakdowns": ["view", "add"],
            "staff-notifications": ["view", "add", "edit"],
            "retrip-requests": ["view"],
        },
        "schedule-setup": {"collection-points": ["view"]},
        "transport-masters": {"vehicle-creation": ["view"], "vehicle-type": ["view"]},
    },
    "supervisor": {
        "schedule-operations": {
            "daily-trip-assignments": ["view", "edit"],
            "daily-trip-collection-points": ["view"],
            "daily-trip-logs": ["view"],
            "householdcollection-events": ["view"],
            "secondary-bin-collection-events": ["view"],
            "wastecollections": ["view"],
            "vehicle-breakdowns": ["view", "edit"],
            "staff-notifications": ["view", "add", "edit"],
            "retrip-requests": ["view", "add"],
        },
        "schedule-setup": {
            "staff-templates": ["view", "add", "edit"],
            "alternative-staff-templates": ["view", "add"],
            "collection-points": ["view"],
            "trip-plans": ["view"],
        },
        "customers": {"customercreations": ["view"]},
        "transport-masters": {"vehicle-creation": ["view"]},
        # Every ticket action (resolve/escalate/assign/status) is a POST, which
        # HTTP_ACTION_MAP scores as "add", not "edit".
        "complaint-ticket": {"tickets": ["view", "add", "edit"]},
    },
}
