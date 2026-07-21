from datetime import time
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation, StaffcreationOfficeDetails


class VehicleBreakdownSeeder(BaseSeeder):
    name = "vehicle_breakdown"

    # (reason, status, approval_status)
    SCENARIOS = [
        ("FLAT_TYRE", VehicleBreakdown.STATUS_REPLACEMENT_ARRANGED, VehicleBreakdown.APPROVAL_APPROVED),
        ("ENGINE_FAILURE", VehicleBreakdown.STATUS_REPORTED, VehicleBreakdown.APPROVAL_PENDING),
        ("ACCIDENT", VehicleBreakdown.STATUS_REJECTED, VehicleBreakdown.APPROVAL_REJECTED),
    ]

    def run(self):
        assignments = list(
            DailyTripAssignment.objects.filter(is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .exclude(vehicle_breakdown__isnull=False)
            .select_related("vehicle_id", "trip_plan_id__vehicle_id")
            .order_by("-trip_date", "-scheduled_time")[: len(self.SCENARIOS)]
        )
        if not assignments:
            self.log("VehicleBreakdownSeeder skipped (no assignments without a breakdown).")
            return

        vehicles = list(VehicleCreation.objects.filter(is_deleted=False).order_by("vehicle_no"))
        staff = list(Staffcreation.objects.filter(is_deleted=False).order_by("staff_unique_id")[:4])
        if len(vehicles) < 2 or len(staff) < 2:
            self.log("VehicleBreakdownSeeder skipped (need at least 2 vehicles and 2 staff).")
            return

        approver = StaffcreationOfficeDetails.objects.filter(is_deleted=False).first()
        created = 0

        for idx, assignment in enumerate(assignments):
            reason, status, approval = self.SCENARIOS[idx % len(self.SCENARIOS)]
            broken_vehicle = assignment.vehicle_id or getattr(assignment.trip_plan_id, "vehicle_id", None)
            if not broken_vehicle:
                continue
            replacement = next(
                (v for v in vehicles if v.unique_id != broken_vehicle.unique_id), None
            )
            if not replacement:
                continue

            VehicleBreakdown.objects.create(
                trip_assignment_id=assignment,
                breakdown_vehicle_id=broken_vehicle,
                replacement_vehicle_id=replacement,
                replacement_driver_id=staff[idx % len(staff)],
                replacement_operator_id=staff[(idx + 1) % len(staff)],
                breakdown_time=time(8 + idx, 15),
                breakdown_lat=Decimal("11.3410") + Decimal(idx) * Decimal("0.01"),
                breakdown_lng=Decimal("77.7172") + Decimal(idx) * Decimal("0.01"),
                breakdown_location=f"NH-544 km {12 + idx}, Erode",
                collected_weight_before_breakdown_kg=Decimal("120.50") + Decimal(idx * 40),
                breakdown_reason=reason,
                breakdown_remarks=f"Seeder demo breakdown ({reason.replace('_', ' ').title()}).",
                status=status,
                approval_status=approval,
                approved_by=approver if approval == VehicleBreakdown.APPROVAL_APPROVED else None,
                approved_at=timezone.now() if approval == VehicleBreakdown.APPROVAL_APPROVED else None,
                rejection_remarks="Replacement vehicle unavailable." if approval == VehicleBreakdown.APPROVAL_REJECTED else None,
            )
            created += 1
            self.log(f"Created VehicleBreakdown ({reason}, {approval}) on {assignment.unique_id}")

        self.log(f"---Vehicle breakdowns seeded ({created} created)---")
