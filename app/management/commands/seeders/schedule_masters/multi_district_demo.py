import math
from datetime import time, timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class MultiDistrictTripDataSeeder(BaseSeeder):
    """Seed a month of trip history for any district that has none yet.

    Erode was the only district with demo DailyTripAssignment/DailyTripLog
    data (see SupervisorMonthDataSeeder), so any state leader dashboard's
    per-district comparison showed just one district. Rather than hardcode
    a district list per state, this seeder auto-discovers every District
    (across every State) that already has a Corporation but zero
    DailyTripLog rows, and gives it the same kind of history — so running
    it again after new states/districts are seeded (e.g. Telangana) picks
    up exactly the new ones and leaves already-seeded districts untouched.

    None of StaffTemplate / VehicleCreation / WasteType / Property are
    geo-scoped in this schema, so they're reused as-is per district — only
    a Collection_point and two TripPlans (bin + household, at the
    district's Corporation) are created per district, then a month of
    Assignments + Logs per plan, mirroring SupervisorMonthDataSeeder's
    weight-generation shape.

    We deliberately DON'T create BinCollectionEvent / WasteCollection rows,
    so the weights set on the log are preserved (the log's post-save sync
    only overrides when those source rows exist).
    """

    name = "multi_district_demo"

    DAYS = 30
    DEFAULT_CAPACITY = Decimal("1000")
    FALLBACK_LAT_LON = (Decimal("11.0"), Decimal("78.0"))

    def _district_lat_lon(self, district):
        """Pull a lat/lon pair out of District.coordinates (set by the
        district/masters seeders); fall back to a generic TN-ish point."""
        points = district.coordinates or []
        if points and isinstance(points[0], dict) and "latitude" in points[0]:
            return Decimal(str(points[0]["latitude"])), Decimal(str(points[0]["longitude"]))
        return self.FALLBACK_LAT_LON

    def _weights_for(self, capacity, day_index, trip_date, seed_offset):
        """Deterministic, natural-looking bin + household weights for a day."""
        seasonal = 0.5 + 0.5 * math.sin((day_index + seed_offset) / 4.5)
        trend = day_index / (self.DAYS * 3.0)
        factor = 0.45 + 0.30 * seasonal + trend
        if trip_date.weekday() >= 5:
            factor *= 0.6
        factor = min(factor, 0.9)

        bin_weight = (capacity * Decimal(str(round(factor, 4)))).quantize(Decimal("0.01"))
        bin_weight = min(bin_weight, capacity - Decimal("1"))

        household = Decimal(str(round(70 + 180 * seasonal, 2)))
        if trip_date.weekday() >= 5:
            household = (household * Decimal("0.7")).quantize(Decimal("0.01"))
        return bin_weight, household

    def run(self):
        templates = list(
            StaffTemplate.objects.filter(
                is_deleted=False, status=StaffTemplate.Status.ACTIVE
            )
            .exclude(driver_id__isnull=True)
            .exclude(operator_id__isnull=True)
            .order_by("created_at")
        )
        if not templates:
            self.log("No usable StaffTemplates (with driver+operator) found — skipping.")
            return

        vehicles = list(VehicleCreation.objects.filter(is_deleted=False).order_by("vehicle_no"))
        if not vehicles:
            self.log("No vehicles found — skipping.")
            return

        bin_waste_type = WasteType.objects.filter(waste_type_name="Dry Waste", is_deleted=False).first()
        household_waste_type = WasteType.objects.filter(waste_type_name="Organic Waste", is_deleted=False).first()
        if not bin_waste_type or not household_waste_type:
            self.log("Required WasteTypes ('Dry Waste' / 'Organic Waste') not found — skipping.")
            return

        supervisor = StaffcreationOfficeDetails.objects.filter(is_deleted=False).first()
        property_obj = Property.objects.filter(property_name="Residential", is_deleted=False).first()
        sub_property = (
            SubProperty.objects.filter(
                property_id=property_obj, sub_property_name="Apartment", is_deleted=False
            ).first()
            if property_obj
            else None
        )

        already_seeded_district_ids = set(
            DailyTripLog.objects.filter(is_deleted=False, district_id__isnull=False)
            .values_list("district_id", flat=True)
            .distinct()
        )
        districts = list(
            District.objects.filter(is_deleted=False)
            .exclude(unique_id__in=already_seeded_district_ids)
            .select_related("state_id")
            .order_by("state_id__name", "name")
        )
        if not districts:
            self.log("No unseeded districts found (every district already has trip logs) — nothing to do.")
            return

        today = timezone.localdate()
        total_assignments = 0
        total_logs = 0

        for idx, district in enumerate(districts):
            district_name = f"{district.name} ({district.state_id.name})"

            corporation = Corporation.objects.filter(district_id=district, is_deleted=False).first()
            if not corporation:
                self.log(f"No Corporation found for '{district_name}' — skipping.")
                continue

            lat, lon = self._district_lat_lon(district)
            cp, _ = Collection_point.objects.update_or_create(
                cp_name=f"CP-{district.name}-Corp-01",
                defaults={
                    "state": district.state_id,
                    "district": district,
                    "area_type": corporation.area_type_id,
                    "corporation": corporation,
                    "municipality": None,
                    "town_panchayat": None,
                    "panchayat_union": None,
                    "panchayat": None,
                    "latitude": lat,
                    "longitude": lon,
                    "coordinates": coordinates((lat, lon), (lat + Decimal("0.002"), lon + Decimal("0.002"))),
                    "is_active": True,
                    "is_deleted": False,
                },
            )

            plans = []
            for plan_idx, (collection_type, waste_type, sched_time) in enumerate([
                (TripPlan.COLLECTION_TYPE_BIN, bin_waste_type, time(7, 0)),
                (TripPlan.COLLECTION_TYPE_HOUSEHOLD, household_waste_type, time(9, 0)),
            ]):
                template = templates[(idx * 2 + plan_idx) % len(templates)]
                vehicle = vehicles[(idx * 2 + plan_idx) % len(vehicles)]
                plan, _ = TripPlan.objects.update_or_create(
                    district=district,
                    corporation=corporation,
                    panchayat=None,
                    collection_type=collection_type,
                    is_deleted=False,
                    defaults={
                        "waste_type_id": waste_type,
                        "state": district.state_id,
                        "area_type": corporation.area_type_id,
                        "staff_template_id": template,
                        "vehicle_id": vehicle,
                        "supervisor_id": supervisor,
                        "property_id": property_obj,
                        "sub_property_id": sub_property,
                        "scheduled_time": sched_time,
                        "trip_trigger_weight_kg": 150,
                        "max_vehicle_capacity_kg": int(vehicle.capacity) if vehicle.capacity else 4000,
                        "approval_status": TripPlan.ApprovalStatus.APPROVED,
                        "status": TripPlan.Status.ACTIVE,
                        "is_active": True,
                        "is_auto_assign": True,
                        "repeat_days": [0, 1, 2, 3, 4, 5, 6],
                    },
                )
                plan.waste_types.set([waste_type])
                plans.append(plan)

            for plan in plans:
                template = plan.staff_template_id
                vehicle = plan.vehicle_id
                capacity = (
                    (vehicle.capacity if vehicle and vehicle.capacity else None)
                    or (Decimal(str(plan.max_vehicle_capacity_kg)) if plan.max_vehicle_capacity_kg else None)
                    or self.DEFAULT_CAPACITY
                )
                scheduled_time = plan.scheduled_time or time(7, 0)

                for offset in range(1, self.DAYS + 1):
                    trip_date = today - timedelta(days=offset)

                    assignment, was_created = DailyTripAssignment.objects.get_or_create(
                        trip_plan_id=plan,
                        trip_date=trip_date,
                        scheduled_time=scheduled_time,
                        is_deleted=False,
                        defaults={
                            "staff_template_id": template,
                            "waste_type_id": plan.waste_type_id,
                            "vehicle_id": plan.vehicle_id,
                            "state": plan.state,
                            "district": plan.district,
                            "area_type": plan.area_type,
                            "corporation": plan.corporation,
                            "municipality": plan.municipality,
                            "town_panchayat": plan.town_panchayat,
                            "panchayat_union": plan.panchayat_union,
                            "panchayat": plan.panchayat,
                            "status": DailyTripAssignment.STATUS_COMPLETED,
                            "approval_status": DailyTripAssignment.APPROVAL_APPROVED,
                        },
                    )
                    if was_created:
                        total_assignments += 1
                    elif assignment.status == DailyTripAssignment.STATUS_CANCELLED:
                        continue

                    if DailyTripLog.objects.filter(trip_assignment_id=assignment, is_deleted=False).exists():
                        continue

                    bin_weight, household = self._weights_for(capacity, offset, trip_date, seed_offset=idx * 3)

                    DailyTripLog.objects.create(
                        trip_assignment_id=assignment,
                        collected_weight_kg=bin_weight,
                        household_collected_weight_kg=household,
                        log_status=DailyTripLog.LOG_STATUS_SUBMITTED,
                        remarks=f"Multi-district demo trip log for {district_name} on {trip_date.isoformat()}",
                    )
                    total_logs += 1

            self.log(f"Seeded {district_name}: {len(plans)} trip plans, collection point '{cp.cp_name}'.")

        self.log(
            "---Multi-district demo data seeded | "
            f"Assignments created: {total_assignments} | Logs created: {total_logs}---"
        )
