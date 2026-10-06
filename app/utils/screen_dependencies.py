"""APIs a sidebar page calls besides its own, so one checkbox covers the page.

Modelled on iwms-private's screen_dependencies.py. The permission catalog
(app/utils/permission_catalog.py) gives each screen the routes it owns; a page
is usually built from more than that — My Tasks resolves tickets through the
tickets API, and nearly every form fills its dropdowns from other masters.
Without this map an admin has to tick every one of those resources as well,
and nothing tells them which.

Keyed by the owning screen as (mainscreen_name, userscreen_name) — the same
names the permission seeder creates and Staff Access Configuration ticks.
Resources are "<url-module>/<route>", exactly as the frontend's
`adminEndpoints` spells them.

- "includes": child resources the page writes through. A grant on the owner
  authorizes the SAME action on them (edit owner -> edit child).
- "lookups": dropdown / reference sources. Any grant on the owner authorizes a
  read of them, never a write — writes still need the resource's own screen.

Only protected modules matter here (see PROTECTED_MODULES in
module_permission_middleware.py); unprotected groups are reachable by any
authenticated user already.
"""

from app.utils import permission_catalog as _catalog

# hooks/useGeoHierarchy.ts (HierarchyFilterBar) and LocationHierarchyFields.
_GEO_LOOKUPS = (
    "common-masters/countries",
    "common-masters/states",
    "masters/districts",
    "masters/areatypes",
    "masters/corporations",
    "masters/municipalities",
    "masters/town-panchayats",
    "masters/panchayat-unions",
    "masters/panchayat",
)
_GEO_WARD_LOOKUPS = _GEO_LOOKUPS + ("masters/wards",)

# The complaint masters' shared MasterForm fills these dropdowns (private's
# _COMPLAINT_MASTER_LOOKUPS).
_COMPLAINT_MASTER_LOOKUPS = (
    "complaint-ticket/modules",
    "complaint-ticket/categories",
    "complaint-ticket/subcategories",
    "complaint-ticket/priorities",
    "complaint-ticket/sources",
    "complaint-ticket/statuses",
)

_LOCAL_BODY_PARENTS = (
    "common-masters/states",
    "masters/districts",
    "masters/areatypes",
)

SCREEN_DEPENDENCIES = {
    # ---------------- common masters ----------------
    ("common-masters", "country"): {"lookups": ("common-masters/continents",)},
    ("common-masters", "state"): {
        "lookups": ("common-masters/continents", "common-masters/countries"),
    },

    # ---------------- location masters ----------------
    ("location-masters", "district"): {"lookups": ("common-masters/states",)},
    ("location-masters", "area-type"): {
        "lookups": ("common-masters/states", "masters/districts"),
    },
    ("location-masters", "corporation"): {"lookups": _LOCAL_BODY_PARENTS},
    ("location-masters", "municipality"): {"lookups": _LOCAL_BODY_PARENTS},
    ("location-masters", "town-panchayat"): {"lookups": _LOCAL_BODY_PARENTS},
    ("location-masters", "panchayat-union"): {"lookups": _LOCAL_BODY_PARENTS},
    ("location-masters", "plb"): {"lookups": _LOCAL_BODY_PARENTS},
    ("location-masters", "ward"): {"lookups": _LOCAL_BODY_PARENTS},
    ("leader-management", "plb-leader-creation"): {"lookups": ("masters/panchayat",)},
    ("leader-management", "district-leader-creation"): {"lookups": ("masters/districts",)},
    ("leader-management", "state-leader-creation"): {"lookups": ("common-masters/states",)},

    # ---------------- waste masters ----------------
    ("waste-masters", "waste-type"): {"lookups": ("complaint-ticket/priorities",)},
    ("waste-masters", "subproperty"): {"lookups": ("waste-types/properties",)},
    ("waste-masters", "bin-creation"): {
        "lookups": _GEO_WARD_LOOKUPS + (
            "schedule-setup/collection-points",
            "waste-types/wastetypes",
        ),
    },

    # ---------------- transport ----------------
    ("transport-masters", "vehicle-creation"): {
        "lookups": _GEO_LOOKUPS + (
            "transport-masters/fuels",
            "transport-masters/vehicle-type",
        ),
    },

    # ---------------- customers ----------------
    ("customer-masters", "customer-creation"): {
        "lookups": _GEO_WARD_LOOKUPS + (
            "waste-types/wastetypes",
            "waste-types/properties",
            "waste-types/subproperties",
            "screen-managements/app-modules",
        ),
    },

    # Frontend-only page over the customer list.
    ("customer-masters", "apartment-list"): {
        "lookups": ("customer-masters/customercreations",),
    },

    # ---------------- screen management / roles / staff ----------------
    ("screen-management", "mainscreen"): {
        "lookups": ("screen-managements/mainscreentype",),
    },
    ("screen-management", "user-screen"): {
        "lookups": ("screen-managements/mainscreens",),
    },
    ("screen-management", "user-screen-permission"): {
        "lookups": _GEO_LOOKUPS + (
            "screen-managements/mainscreens",
            "screen-managements/userscreens",
            "screen-managements/userscreen-action",
        ),
    },
    ("role-management", "staff-user-type"): {"lookups": ("role-assigns/user-type",)},
    ("role-management", "staff-hierarchy"): {
        "lookups": ("role-assigns/governmentusertypes",),
    },
    ("staff-management", "staff-creation"): {
        "lookups": _GEO_LOOKUPS + (
            "role-assigns/staffusertypes",
            "role-assigns/contractorusertypes",
            "role-assigns/governmentusertypes",
            "masters/departments",
            "masters/designations",
            "screen-managements/app-modules",
        ),
    },
    ("staff-management", "staff-access-configuration"): {
        "lookups": _GEO_WARD_LOOKUPS + (
            "role-assigns/user-type",
            "role-assigns/governmentusertypes",
            "screen-managements/mainscreens",
            "screen-managements/userscreens",
            "screen-managements/userscreen-action",
            "screen-managements/userscreenpermissions",
            "screen-managements/dashboard-widget-permissions",
        ),
    },
    ("staff-management", "staff-access-dashboard"): {
        "lookups": ("schedule-masters/daily-waste-comparisons",),
    },

    # ---------------- schedule setup ----------------
    ("schedule-setup", "staff-template"): {
        "lookups": ("user-creations/staffcreation",),
    },
    ("schedule-setup", "alternative-staff-template"): {
        "lookups": (
            "schedule-setup/staff-templates",
            "user-creations/staffcreation",
        ),
    },
    ("schedule-setup", "collection-point"): {
        "lookups": _GEO_WARD_LOOKUPS + ("waste-types/wastetypes",),
    },
    ("schedule-setup", "trip-plans"): {
        "lookups": _GEO_WARD_LOOKUPS + (
            "waste-types/wastetypes",
            "waste-types/bins",
            "schedule-setup/staff-templates",
            "schedule-setup/collection-points",
            "user-creations/staffcreation",
            "transport-masters/vehicle-creation",
            "customer-masters/customercreations",
        ),
    },

    # ---------------- daily operations ----------------
    # The daily trip plan's three tables are its own routes (catalog); these
    # are what its Assignment form and Tracking page read besides.
    ("daily-operations", "daily-trip-plan"): {
        "lookups": _GEO_WARD_LOOKUPS + (
            "waste-types/wastetypes",
            "waste-types/bins",
            "schedule-setup/trip-plans",
            "schedule-setup/staff-templates",
            "schedule-setup/alternative-staff-templates",
            "schedule-setup/collection-points",
            "customer-masters/customercreations",
        ),
    },
    # Frontend-only page: everything it reads is a lookup (its tracking /
    # optimize-route actions are permission-exempt on the viewset).
    ("daily-operations", "daily-trip-tracking"): {
        "lookups": (
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/daily-trip-collection-points",
            "schedule-setup/staff-templates",
            "schedule-setup/alternative-staff-templates",
            "schedule-setup/collection-points",
            "masters/panchayat",
        ),
    },
    ("daily-operations", "secondary-bin-collection-event"): {
        "lookups": _GEO_WARD_LOOKUPS + (
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/daily-trip-collection-points",
            "waste-types/bins",
        ),
    },
    ("daily-operations", "household-collection-event"): {
        "lookups": _GEO_WARD_LOOKUPS + (
            "schedule-operations/daily-trip-assignments",
            "schedule-operations/daily-trip-household-collections",
            "customer-masters/customercreations",
        ),
    },
    ("daily-operations", "vehicle-breakdown"): {
        "lookups": ("schedule-operations/daily-trip-assignments",),
    },
    # The trip log report page moves the trip on ("proceed-next-trip", a
    # POST on the assignment).
    ("daily-operations", "daily-trip-logs"): {
        "includes": ("schedule-operations/daily-trip-assignments",),
        "lookups": _GEO_LOOKUPS + (
            "schedule-operations/daily-trip-household-collections",
            "waste-types/wastetypes",
        ),
    },

    # ---------------- complaints ----------------
    ("complaint-management", "complaint-tickets"): {
        "lookups": _GEO_LOOKUPS + (
            "complaint-ticket/statuses",
            "complaint-ticket/categories",
            "complaint-ticket/subcategories",
            "complaint-ticket/priorities",
            "complaint-ticket/sources",
            "customer-masters/customercreations",
            "waste-types/wastetypes",
        ),
    },
    # Resolve / reopen are POSTs on the tickets API.
    ("complaint-management", "my-tasks"): {
        "includes": ("complaint-ticket/tickets",),
        "lookups": _GEO_LOOKUPS,
    },
    # The Reference Data and Categories pages.
    ("complaint-management", "reference-data"): {"lookups": _COMPLAINT_MASTER_LOOKUPS},
    ("complaint-management", "categories"): {"lookups": _COMPLAINT_MASTER_LOOKUPS},
    ("complaint-management", "sla-rules"): {
        "lookups": _GEO_LOOKUPS + _COMPLAINT_MASTER_LOOKUPS,
    },
    ("complaint-reports", "complaints-report"): {"lookups": _GEO_WARD_LOOKUPS},

    # ---------------- reports / audits / attendance ----------------
    ("waste-reports", "daily-waste-comparison"): {"lookups": _GEO_WARD_LOOKUPS},
    ("waste-reports", "monthly-waste-comparison"): {"lookups": _GEO_WARD_LOOKUPS},
    ("audits", "common-audit"): {
        "lookups": (
            "screen-managements/mainscreens",
            "screen-managements/userscreens",
        ),
    },
    ("attendance", "attendance"): {"lookups": ("user-creations/staffcreation",)},
}


def _validate():
    for (module_name, screen_name) in SCREEN_DEPENDENCIES:
        if screen_name not in _catalog.SCREEN_STRUCTURE.get(module_name, ()):
            raise ValueError(
                f"SCREEN_DEPENDENCIES owner {(module_name, screen_name)!r} is "
                "not a screen in permission_catalog.py."
            )


def _index(kind):
    index = {}
    for owner, deps in SCREEN_DEPENDENCIES.items():
        for resource in deps.get(kind, ()):
            index.setdefault(resource, []).append(owner)
    return index


_validate()

# "<url-module>/<route>" -> [(mainscreen, userscreen), ...] depending on it.
INCLUDED_BY = _index("includes")
LOOKUP_FOR = _index("lookups")
