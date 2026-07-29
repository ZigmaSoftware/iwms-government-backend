"""Extra demo households on driver_user's OWN household trip.

`DriverUserSeeder` builds driver_user's household TripPlan as an *area* stop
(``customer_id=None``), so the assignment signal fans it out to every active,
non-bulk customer in the plan's panchayat **and** selected wards. The stock
`CustomerCreationSeeder` only creates 2 customers per ward, which leaves the
mobile household flow with a 2-stop list — too thin to exercise the timeline,
progress meter, pagination or the collect/skip/not-available paths.

This seeder adds a richer set of households in the EXACT same geo hierarchy
driver_user's household plan already targets (state -> district -> area_type ->
panchayat -> ward), so they are picked up by that same fan-out and nothing else
in the tree has to change. It then re-syncs today's household assignment(s),
because the fan-out signal only fires on assignment *creation* — on a same-day
re-run the assignment already exists and would otherwise never see the new
households.

Runs after `DriverUserSeeder` (which creates the plan + today's assignment) and
after `CustomerUserSeeder`. Fully idempotent: households are keyed by a stable
``id_no``, and the daily fan-out uses ``get_or_create``.
"""

from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import spread_points
from app.management.commands.seeders.tn_geo_data import STREET_NAMES, TAMIL_NAME_POOL
from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.signals.trip_plan_signals import sync_daily_assignment_stops_from_plan

# Same 4 segregated streams every household route handles project-wide
# (TripPlanSeeder / CustomerCreationSeeder / DriverUserSeeder agree on this).
HOUSEHOLD_WASTE_TYPES = ["Wet Waste", "Dry Waste", "Mixed Waste", "Sanitary Waste"]

# Same convention as CustomerUserSeeder / CustomerCreationSeeder.
DEFAULT_PASSWORD = "Customer1"

# Household mix. `kind` drives Property/SubProperty selection:
#   house     -> Residential / Individual House
#   apartment -> Residential / Apartment (flats share one apartment block, so
#                the app's apartment/group-QR grouping has real data)
#   shop      -> Commercial / Shop (a non-residential stop on the same route)
# Kept well under the bulk-waste thresholds so every row stays a *household*
# stop (`is_bulkwaste_generator=False`) — a bulk row would be excluded from the
# household fan-out entirely.
HOUSEHOLD_MIX = [
    {"kind": "house", "member_count": 4, "sqft": 1200},
    {"kind": "house", "member_count": 3, "sqft": 950},
    {"kind": "house", "member_count": 6, "sqft": 1600},
    {"kind": "house", "member_count": 2, "sqft": 800},
    {"kind": "house", "member_count": 5, "sqft": 1400},
    {"kind": "house", "member_count": 3, "sqft": 1050},
    {"kind": "house", "member_count": 7, "sqft": 1800},
    {"kind": "house", "member_count": 4, "sqft": 1150},
    {"kind": "apartment", "member_count": 3, "sqft": 900, "flat_no": "101"},
    {"kind": "apartment", "member_count": 4, "sqft": 950, "flat_no": "102"},
    {"kind": "apartment", "member_count": 2, "sqft": 850, "flat_no": "201"},
    {"kind": "shop", "member_count": None, "sqft": 600},
]

APARTMENT_NAME = "Kaveri Residency"
APARTMENT_BLOCK = "A"

ID_PROOF_CYCLE = ["AADHAAR", "VOTER_ID", "PAN_CARD"]

# Coordinate spread around the route centre — map cosmetics only; the household
# flow matches on panchayat/ward, never on distance.
SPREAD_RADIUS_KM = 0.35

# Fallback centre: Anthiyur / Modakkurichi belt, matching DriverUserSeeder.
FALLBACK_CENTER = (11.5793, 77.5900)
FALLBACK_PINCODE = "638501"


class DriverHouseholdCustomerSeeder(BaseSeeder):
    name = "DriverHouseholdCustomerSeeder"

    DRIVER_USERNAME = "driver_user"

    # ------------------------------------------------------------------
    def run(self):
        plan = self._driver_household_plan()
        if plan is None:
            self.log(
                f"No active household TripPlan for '{self.DRIVER_USERNAME}' — "
                f"run DriverUserSeeder first. Skipping."
            )
            return

        property_map = self._resolve_properties()
        if property_map is None:
            return

        waste_types = list(
            WasteType.objects.filter(
                waste_type_name__in=HOUSEHOLD_WASTE_TYPES, is_deleted=False
            )
        )
        if not waste_types:
            self.log("Household WasteTypes missing — run WasteTypeSeeder first. Skipping.")
            return

        # The fan-out narrows to the plan's selected wards (an empty selection
        # means "the whole local body"), and a later re-sync DELETES pending
        # household rows whose customer sits outside those wards. So the new
        # households must carry the plan's own ward, not just its panchayat.
        ward = plan.wards.filter(is_deleted=False).order_by("ward_name").first()
        center = self._route_center(plan, ward)
        pincode = self._route_pincode(plan, ward)
        area_name = ward.ward_name if ward else (
            plan.panchayat.panchayat_name if plan.panchayat else "Demo Area"
        )

        points = spread_points(
            center[0], center[1], len(HOUSEHOLD_MIX), radius_km=SPREAD_RADIUS_KM
        )
        # Every apartment flat must share one coordinate: the model derives
        # `apartment_unique_id` from (apartment_name, latitude, longitude), so
        # differing coordinates would split one block into separate apartments.
        apartment_point = next(
            (
                points[idx]
                for idx, spec in enumerate(HOUSEHOLD_MIX)
                if spec["kind"] == "apartment"
            ),
            points[0],
        )

        created = updated = 0
        for idx, spec in enumerate(HOUSEHOLD_MIX):
            lat, lon = apartment_point if spec["kind"] == "apartment" else points[idx]
            prop, sub_prop = property_map[spec["kind"]]
            id_no = f"DRVHH-CUST-{idx + 1:03d}"
            contact = f"979{idx + 1:07d}"
            name = TAMIL_NAME_POOL[idx % len(TAMIL_NAME_POOL)]

            defaults = {
                "customer_name": f"{name} (HH-{idx + 1:02d})",
                "contact_no": contact,
                "username": contact,
                "password": make_password(DEFAULT_PASSWORD),
                "building_no": str(20 + idx),
                "street": STREET_NAMES[idx % len(STREET_NAMES)],
                "area": area_name,
                "pincode": pincode,
                "latitude": f"{lat:.6f}",
                "longitude": f"{lon:.6f}",
                "id_proof_type": ID_PROOF_CYCLE[idx % len(ID_PROOF_CYCLE)],
                "property_ref": prop,
                "sub_property": sub_prop,
                "member_count": spec["member_count"],
                "sqft": spec["sqft"],
                "water_consumption_lpd": None,
                "waste_collection_kg_per_day": None,
                "is_bulkwaste_generator": False,
                # Geo copied straight off the plan so the household fan-out's
                # geo filter matches exactly (it compares the most specific
                # populated field, not the ancestor chain).
                "state": plan.state,
                "district": plan.district,
                "area_type": plan.area_type,
                "corporation": plan.corporation,
                "municipality": plan.municipality,
                "town_panchayat": plan.town_panchayat,
                "panchayat_union": plan.panchayat_union,
                "panchayat": plan.panchayat,
                "ward": ward,
                # Apartment identity only for the apartment flats; every other
                # kind must clear these or the model groups them into a block.
                "apartment_name": APARTMENT_NAME if spec["kind"] == "apartment" else None,
                "block_no": APARTMENT_BLOCK if spec["kind"] == "apartment" else None,
                "flat_no": spec.get("flat_no"),
                "apartment_unique_id": None,
                "villa_no": None,
                "industry_name": None,
                "industry_type": None,
                "is_active": True,
                "is_deleted": False,
            }

            customer, was_created = CustomerCreation.objects.update_or_create(
                id_no=id_no, defaults=defaults
            )
            customer.waste_types.set(waste_types)
            if was_created:
                created += 1
            else:
                updated += 1

        added = self._resync_household_assignments(plan)

        self.log(
            f"---driver_user households: {created} created, {updated} updated in "
            f"{area_name} ({plan.panchayat.panchayat_name if plan.panchayat else '—'}) | "
            f"{added} new daily stop(s) fanned out---"
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _driver_household_plan(self):
        """driver_user's own active household plan. Matches DriverUserSeeder's
        deterministic single template (driver_id=driver_user)."""
        driver = Staffcreation.objects.filter(
            username=self.DRIVER_USERNAME, is_deleted=False
        ).first()
        if not driver:
            return None
        templates = StaffTemplate.objects.filter(driver_id=driver, is_deleted=False)
        return (
            TripPlan.objects.filter(
                staff_template_id__in=templates,
                collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                is_deleted=False,
            )
            .select_related("panchayat", "state", "district", "area_type")
            .order_by("unique_id")
            .first()
        )

    def _resolve_properties(self):
        """{kind: (Property, SubProperty)} or None when a master is missing."""
        wanted = {
            "house": ("Residential", "Individual House"),
            "apartment": ("Residential", "Apartment"),
            "shop": ("Commercial", "Shop"),
        }
        resolved = {}
        for kind, (prop_name, sub_name) in wanted.items():
            prop = Property.objects.filter(
                property_name=prop_name, is_deleted=False
            ).first()
            sub = (
                SubProperty.objects.filter(
                    property_id=prop, sub_property_name=sub_name, is_deleted=False
                ).first()
                if prop
                else None
            )
            if not prop or not sub:
                self.log(
                    f"'{prop_name} / {sub_name}' missing — run PropertySeeder + "
                    f"SubPropertySeeder first. Skipping."
                )
                return None
            resolved[kind] = (prop, sub)
        return resolved

    def _route_center(self, plan, ward):
        """Centre the new households on the ward's own polygon, else on an
        existing customer already served by this route, else the demo belt."""
        for coord in (ward.coordinates or []) if ward else []:
            try:
                return float(coord["latitude"]), float(coord["longitude"])
            except (KeyError, TypeError, ValueError):
                continue

        neighbour = (
            CustomerCreation.objects.filter(
                panchayat=plan.panchayat, is_deleted=False, is_active=True
            )
            .exclude(latitude="")
            .order_by("unique_id")
            .first()
        )
        if neighbour:
            try:
                return float(neighbour.latitude), float(neighbour.longitude)
            except (TypeError, ValueError):
                pass
        return FALLBACK_CENTER

    def _route_pincode(self, plan, ward):
        neighbour = (
            CustomerCreation.objects.filter(
                panchayat=plan.panchayat, is_deleted=False, is_active=True
            )
            .exclude(pincode="")
            .order_by("unique_id")
            .values_list("pincode", flat=True)
            .first()
        )
        return neighbour or FALLBACK_PINCODE

    def _resync_household_assignments(self, plan):
        """Fan the new households onto every not-yet-finished assignment this
        plan already generated. `copy_trip_plan_stops_to_daily_assignment` only
        fires on assignment creation, so a same-day re-run needs this explicit
        sync. Completed/cancelled trips are left alone — back-filling stops onto
        a finished trip would reopen it."""
        assignments = DailyTripAssignment.objects.filter(
            trip_plan_id=plan, is_deleted=False
        ).exclude(
            status__in=[
                DailyTripAssignment.STATUS_COMPLETED,
                DailyTripAssignment.STATUS_CANCELLED,
            ]
        )
        added = 0
        for assignment in assignments:
            added += sync_daily_assignment_stops_from_plan(assignment)
            total = DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            ).count()
            self.log(f"{assignment.unique_id}: {total} household stop(s)")
        return added
