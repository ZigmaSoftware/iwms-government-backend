from datetime import time

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.management.commands.seeders.ward_utils import (
    geo_defaults_for_local_body,
    local_bodies_for_district,
    wards_for_local_body,
)
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails
from app.models.masters.waste_masters.wastetype import WasteType

# Household collection only ever handles these 4 segregated streams.
HOUSEHOLD_WASTE_TYPES = ["Wet Waste", "Dry Waste", "Mixed Waste", "Sanitary Waste"]
# Bin (secondary collection point) routes can carry any of the 9 types —
# matches whatever the ward's collection point actually has bins for.
BIN_WASTE_TYPES = [
    "Organic Waste", "Plastic Waste", "Paper Waste", "Metal Waste", "Hazardous Waste",
    "Wet Waste", "Dry Waste", "Mixed Waste", "Sanitary Waste",
]


class TripPlanSeeder(BaseSeeder):
    """One bin_collection + one household_collection TripPlan per Ward.
    Each ward's pair draws its own never-reused staff template and vehicle
    from its parent local body's dedicated pool (StaffTemplateSeeder /
    VehicleCreationSeeder create exactly ward_count x 2 of each per local
    body, in the same order consumed here) — mirroring real dispatch, where
    a local body owns a fleet/crew roster and assigns one crew + one
    vehicle per route, never double-booking either onto a second route."""

    name = "TripPlanSeeder"

    def run(self):
        household_types = list(
            WasteType.objects.filter(waste_type_name__in=HOUSEHOLD_WASTE_TYPES, is_deleted=False)
        )
        bin_types = list(
            WasteType.objects.filter(waste_type_name__in=BIN_WASTE_TYPES, is_deleted=False)
        )
        if not household_types or not bin_types:
            self.log("WasteTypes not found — run WasteTypeSeeder first.")
            return

        count = 0
        for district_name in DISTRICTS:
            for lb in local_bodies_for_district(district_name):
                count += self._seed_local_body(lb, household_types, bin_types)

        self.log(f"---Trip plans seeded ({count} created)---")

    def _seed_local_body(self, lb, household_types, bin_types):
        parent_type, parent = lb["parent_type"], lb["parent"]
        wards = wards_for_local_body(parent_type, parent)
        if not wards:
            return 0

        templates = list(
            StaffTemplate.objects.filter(**{parent_type: parent}, is_deleted=False).order_by("created_at")
        )
        vehicles = list(
            VehicleCreation.objects.filter(**{parent_type: parent}, is_deleted=False).order_by("created_at")
        )
        needed = len(wards) * 2
        if len(templates) < needed or len(vehicles) < needed:
            self.log(
                f"'{parent}': only {len(templates)} templates / {len(vehicles)} vehicles "
                f"for {needed} ward slots — some wards will be skipped."
            )

        supervisor = StaffcreationOfficeDetails.objects.filter(
            district=parent.district_id, designation="Field Supervisor", is_deleted=False,
        ).first()

        geo_fields = geo_defaults_for_local_body(parent_type, parent)

        created_count = 0
        slot = 0
        for ward_idx, ward in enumerate(wards):
            for collection_type, waste_types, sched_hour in (
                (TripPlan.COLLECTION_TYPE_BIN, bin_types, 6),
                (TripPlan.COLLECTION_TYPE_HOUSEHOLD, household_types, 8),
            ):
                if slot >= len(templates) or slot >= len(vehicles):
                    slot += 1
                    continue
                template = templates[slot]
                vehicle = vehicles[slot]
                slot += 1

                sched_time = time(sched_hour, (ward_idx * 15) % 60)
                max_kg = int(vehicle.capacity or 1500)

                plan, created = TripPlan.objects.update_or_create(
                    staff_template_id=template,
                    vehicle_id=vehicle,
                    collection_type=collection_type,
                    is_deleted=False,
                    defaults={
                        **geo_fields,
                        "supervisor_id": supervisor,
                        "scheduled_time": sched_time,
                        "trip_trigger_weight_kg": max(50, max_kg // 4),
                        "max_vehicle_capacity_kg": max_kg,
                        "approval_status": TripPlan.ApprovalStatus.APPROVED,
                        "status": TripPlan.Status.ACTIVE,
                        "is_active": True,
                        "is_auto_assign": True,
                        "repeat_days": [0, 1, 2, 3, 4, 5, 6],
                    },
                )
                plan.waste_types.set(waste_types)
                plan.wards.set([ward])
                if created:
                    created_count += 1

        return created_count
