from django.conf import settings
from django.core.management.base import BaseCommand

# ============================================================
# IMPORTS — organized by URL group they belong to
# ============================================================

# superadmin (router: superadmin/company, superadmin/project)
from app.management.commands.seeders.superadmin_masters import (
    BluePlanetSeeder,
    COMPANY_SEEDERS,
    PLATFORM_SEEDERS,
)

# common-masters (router: common-masters/continents, countries, states)
from app.management.commands.seeders.common_masters import COMMON_MASTER_SEEDERS as _COMMON_MASTER_SEEDERS

# masters (router: masters/districts, cities, zones, wards, panchayat, ...)
from app.management.commands.seeders.masters import MASTER_SEEDERS as CORE_MASTER_SEEDERS
from app.management.commands.seeders.masters.department import DepartmentSeeder
from app.management.commands.seeders.masters.designation import DesignationSeeder

# waste-types (router: waste-types/properties, subproperties)
from app.management.commands.seeders.waste_types.properties import PropertySeeder
from app.management.commands.seeders.waste_types.subproperties import SubPropertySeeder

# assets (router: assets/waste-types, assets/bins)
from app.management.commands.seeders.waste_types.wastetype import WasteTypeSeeder
from app.management.commands.seeders.assets.bins import BinSeeder

# role-assigns (router: role-assigns/user-type, staffusertypes, contractorusertypes)
from app.management.commands.seeders.role_assigns import ROLE_ASSIGN_SEEDERS

# user-creations (router: user-creations/staffcreation, ...)
from app.management.commands.seeders.user_creations.auth_user_seeder import AuthUserSeeder
from app.management.commands.seeders.user_creations.driver_user import DriverUserSeeder
from app.management.commands.seeders.user_creations.supervisor_user import SupervisorUserSeeder
from app.management.commands.seeders.customers.customer_user import CustomerUserSeeder
from app.management.commands.seeders.user_creations.staff_office import StaffOfficeSeeder
from app.management.commands.seeders.user_creations.staff_personal import StaffPersonalSeeder
from app.management.commands.seeders.user_creations.corporation_access import CorporationAccessSeeder

# transport-masters (router: transport-masters/vehicle-type, vehicle-creation, trip-attendance, fuels)
from app.management.commands.seeders.transport_masters.vehicleTypeCreation import VehicleTypeCreationSeeder
from app.management.commands.seeders.transport_masters.vehicleCreation import VehicleCreationSeeder
from app.management.commands.seeders.transport_masters.fuel import FuelSeeder
from app.management.commands.seeders.transport_masters.trip_attendance import TripAttendanceSeeder

# process-items


# schedule-masters (router: schedule-masters/ — all 9 submodules)
from app.management.commands.seeders.schedule_masters.collection_point import CollectionPointSeeder
from app.management.commands.seeders.schedule_masters.staff_template import StaffTemplateSeeder
from app.management.commands.seeders.schedule_masters.alternative_staff_template import AlternativeStaffTemplateSeeder
from app.management.commands.seeders.schedule_masters.trip_plan import TripPlanSeeder
from app.management.commands.seeders.schedule_masters.trip_plan_collection_point import TripPlanCollectionPointSeeder
from app.management.commands.seeders.schedule_masters.daily_trip_assignment import DailyTripAssignmentSeeder
from app.management.commands.seeders.schedule_masters.daily_trip_collection_point import DailyTripCollectionPointSeeder
from app.management.commands.seeders.schedule_masters.daily_trip_household_collection import DailyTripHouseholdCollectionSeeder
from app.management.commands.seeders.schedule_masters.daily_trip_log import DailyTripLogSeeder
from app.management.commands.seeders.schedule_masters.bin_collection_event import BinCollectionEventSeeder
from app.management.commands.seeders.schedule_masters.scheduler_demo import SchedulerDemoSeeder
from app.management.commands.seeders.schedule_masters.vehicle_breakdown import VehicleBreakdownSeeder
from app.management.commands.seeders.schedule_masters.supervisor_month_data import SupervisorMonthDataSeeder
from app.management.commands.seeders.schedule_masters.waste_collection import WasteCollectionSeeder

# screen-managements (router: screen-managements/...)
from app.management.commands.seeders.screen_managements import PERMISSION_SEEDERS
from app.management.commands.seeders.screen_managements.corporation_permissions import (
    CorporationPermissionSeeder,
)

# collections (router: collections/panchayat-wise, ward-wise, zone-wise)
from app.management.commands.seeders.collections import COLLECTION_SEEDERS

# customer-masters (router: customer-masters/customercreations, ...)
from app.management.commands.seeders.customers import CUSTOMER_SEEDERS

# complaint-ticket (router: complaint-ticket/tickets, categories, subcategories, ...)
from app.management.commands.seeders.complaint_ticket import COMPLAINT_TICKET_SEEDERS

# audits (router: audits/vehicle-trip-audit, trip-exception-log, ...)


# reports (router: reports/monthly-waste-comparison)
from app.management.commands.seeders.reports import REPORT_SEEDERS


# ============================================================
# SEED GROUPS — names mirror URL router groups exactly
# ============================================================

SUPERADMIN_SEEDERS = [
    *PLATFORM_SEEDERS,  # super_admin user
    *COMPANY_SEEDERS,   # company + project
]

COMMON_MASTER_SEEDERS = [
    *_COMMON_MASTER_SEEDERS,
]

MASTERS_SEEDERS = [
    *CORE_MASTER_SEEDERS,   # districts, cities, zones, wards, panchayat, etc.
    DepartmentSeeder,
    DesignationSeeder,
]

WASTE_TYPES_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
]

# Note: WasteTypeSeeder (bluetooth waste types) lives in `assets` per the URL group.
# BinSeeder depends on CollectionPoint (schedule-masters), so in `all` mode
# BinSeeder is invoked from within schedule-masters (after CollectionPointSeeder).
# Running `--group assets` alone seeds WasteType only; bins require schedule-masters CPs.
ASSETS_SEEDERS = [
    WasteTypeSeeder,    # assets/waste-types → WasteTypeViewSet
    # BinSeeder runs inside schedule-masters after CollectionPointSeeder
]

ROLE_ASSIGNS_SEEDERS = [
    *ROLE_ASSIGN_SEEDERS,
]

USER_CREATIONS_SEEDERS = [
    StaffOfficeSeeder,         # staff records (+ government user type/role)
    StaffPersonalSeeder,
    AuthUserSeeder,            # auth logins — needs staff (+ govt role) to exist first
    CorporationAccessSeeder,   # corporation admin + supervisor + StaffDataScope
]

TRANSPORT_MASTERS_SEEDERS = [
    VehicleTypeCreationSeeder,   # transport-masters/vehicle-type
    FuelSeeder,                  # transport-masters/fuels (must precede vehicles)
    VehicleCreationSeeder,       # transport-masters/vehicle-creation
]

PROCESS_ITEMS_SEEDERS = [
]

# ============================================================
# SCHEDULE MASTERS — 9 submodules in dependency order
# BinSeeder is included here (after CollectionPointSeeder) because
# bins depend on collection_points which are seeded in this group.
# ============================================================
SCHEDULE_MASTERS_SEEDERS = [
    CollectionPointSeeder,          # 1. collection-points
    BinSeeder,                      # bins (assets dependency — must follow CollectionPoint)
    StaffTemplateSeeder,            # 2. staff-templates
    AlternativeStaffTemplateSeeder, # 3. alternative-staff-templates
    TripPlanSeeder,                 # 4. trip-plans
    TripPlanCollectionPointSeeder,  # 5. trip-plan-collection-points
    DailyTripAssignmentSeeder,      # 6. daily-trip-assignments
    DailyTripCollectionPointSeeder, # 7. daily-trip-collection-points
    DailyTripHouseholdCollectionSeeder,
    DailyTripLogSeeder,             # 8. daily-trip-logs
    TripAttendanceSeeder,
    BinCollectionEventSeeder,       # 9. bin-collection-events
    VehicleBreakdownSeeder,         # 10. vehicle-breakdowns
]

SCREEN_MANAGEMENTS_SEEDERS = [
    *PERMISSION_SEEDERS,
    CorporationPermissionSeeder,   # scoped permissions for Erode corp admin + supervisor
]

COLLECTIONS_SEEDERS = [
    *COLLECTION_SEEDERS,
]

CUSTOMER_MASTERS_SEEDERS = [
    *CUSTOMER_SEEDERS,
    # Household waste-collection records depend on customers (this group) and
    # optionally on daily trip assignments (already seeded in schedule-masters).
    WasteCollectionSeeder,
]

COMPLAINT_TICKET_SEEDER_GROUP = [
    *COMPLAINT_TICKET_SEEDERS,
]


REPORTS_SEEDERS = [
    *REPORT_SEEDERS,
]

# Mobile demo logins — must run last (need today's assignments + customers).
DRIVER_DEMO_SEEDERS = [
    DriverUserSeeder,
    SupervisorUserSeeder,
    SupervisorMonthDataSeeder,  # a month of trips + logs for the supervisor graph
    CustomerUserSeeder,
]

# ============================================================
# ORDER MATTERS — follows URL group dependency chain
# ============================================================
ORDERED_GROUPS = [
    "superadmin",           # company, project, super_admin user
    "common-masters",       # continents, countries, states
    "masters",              # districts, cities, zones, wards, panchayat, ...
    "waste-types",          # properties, subproperties
    "assets",               # WasteType (bins seeded inside schedule-masters)
    "role-assigns",         # user-type, staffusertypes, contractorusertypes
    "user-creations",       # staff office, personal, auth-user
    "transport-masters",    # vehicle-type, vehicle-creation, fuel
    "schedule-masters",     # all 9 submodules (incl. CollectionPoint + Bins internally)
    "screen-managements",   # screen permissions
    "collections",          # panchayat-wise, ward-wise, zone-wise
    "customer-masters",     # customer creations, feedback, charge rules
    "complaint-ticket",     # tickets, categories, teams, sla-rules, routing-rules
    # "audits",               # vehicle-trip-audit, trip-exception-log, ...
    "reports",              # monthly-waste-comparison
    "driver-demo",          # driver_user login wired to a today trip (bin + household)
]

SEED_GROUPS = {
    # Mirrors URL router group names exactly
    "superadmin":         SUPERADMIN_SEEDERS,
    "common-masters":     COMMON_MASTER_SEEDERS,
    "masters":            MASTERS_SEEDERS,
    "waste-types":        WASTE_TYPES_SEEDERS,
    "assets":             ASSETS_SEEDERS,
    "role-assigns":       ROLE_ASSIGNS_SEEDERS,
    "user-creations":     USER_CREATIONS_SEEDERS,
    "user-creation":      USER_CREATIONS_SEEDERS,   # alias
    "transport-masters":  TRANSPORT_MASTERS_SEEDERS,
    "process-items":      PROCESS_ITEMS_SEEDERS,
    "schedule-masters":   SCHEDULE_MASTERS_SEEDERS,
    "screen-managements": SCREEN_MANAGEMENTS_SEEDERS,
    "collections":        COLLECTIONS_SEEDERS,
    "customer-masters":   CUSTOMER_MASTERS_SEEDERS,
    "customers":          CUSTOMER_MASTERS_SEEDERS,  # alias
    "complaint-ticket":   COMPLAINT_TICKET_SEEDER_GROUP,
    "reports":            REPORTS_SEEDERS,
    "driver-demo":        DRIVER_DEMO_SEEDERS,
    # Legacy aliases
    "staff":              USER_CREATIONS_SEEDERS,
    "vehicles":           TRANSPORT_MASTERS_SEEDERS,
    "platform":           SUPERADMIN_SEEDERS,
    # Single-seeder shortcuts
    "scheduler-demo":     [SchedulerDemoSeeder],   # one ready-to-run demo TripPlan for the job scheduler
    "bin-collection-events": [BinCollectionEventSeeder],
    "daily-trip-household-collections": [DailyTripHouseholdCollectionSeeder],
    "waste-collections": [WasteCollectionSeeder],
    "trip-logs":          [DailyTripLogSeeder],
    "supervisor-graph":   [SupervisorMonthDataSeeder],  # month of trips+logs for supervisor_user
    "vehicle-breakdowns": [VehicleBreakdownSeeder],
    "blue-planet":        [BluePlanetSeeder],
}

# ============================================================
# EXPLICIT "ALL" GROUP — ordered for correct dependency chain
# ============================================================
SEED_GROUPS["all"] = [
    seeder
    for group in ORDERED_GROUPS
    for seeder in SEED_GROUPS[group]
]


class Command(BaseCommand):
    help = "Run database seeders"

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            type=str,
            help=(
                "Seeder group (mirrors URL router groups): "
                "superadmin | common-masters | masters | waste-types | assets | "
                "role-assigns | user-creations | transport-masters | process-items | "
                "schedule-masters | screen-managements | collections | customer-masters | "
                "complaint-ticket | audits | reports | all"
            ),
        )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT == "production":
            self.stdout.write(self.style.ERROR("Seeding is disabled in PRODUCTION environment"))
            return

        if not settings.DEBUG:
            self.stdout.write(self.style.ERROR("Seeding blocked because DEBUG=False"))
            return

        group = options.get("group")

        if group:
            if group not in SEED_GROUPS:
                valid = ", ".join(k for k in SEED_GROUPS if k not in ("all",))
                self.stdout.write(self.style.ERROR(f"Invalid group '{group}'. Use one of: {valid}"))
                return
            seeders = SEED_GROUPS[group]
        else:
            seeders = SEED_GROUPS["all"]

        self.stdout.write(self.style.WARNING("Starting database seeding...\n"))

        for seeder_cls in seeders:
            seeder = seeder_cls()
            self.stdout.write(self.style.NOTICE(f"Running {seeder_cls.__name__}"))
            seeder.run()

        self.stdout.write(self.style.SUCCESS("\nSeeding completed successfully."))
