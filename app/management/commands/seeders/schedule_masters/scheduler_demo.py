"""
SchedulerDemoSeeder
===================

Creates ONE self-contained, clearly-named TripPlan ("DEMO Scheduler Trip")
that the Daily Trip Job Scheduler is guaranteed to pick up *today*, plus its
stop list. It then clears any DailyTripAssignment already generated for today
for this plan, so that every time you run the scheduler you can WATCH it
create fresh Daily Trip Points.

This is a *demo* seeder — it is idempotent and only touches its own demo plan
(matched by a marker in custom-ish fields). It never deletes real data.

Run it on its own:
    python manage.py seed --only SchedulerDemoSeeder      # if --only is supported
    # or simply run the full schedule_masters group:
    python manage.py seed --group schedule_masters

Then exercise the scheduler:
    python manage.py generate_daily_trips                 # generates today's trips
    python manage.py generate_daily_trips                 # run again → all skipped (no dupes)
"""
from datetime import time

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.district import District
from app.models.masters.corporation import Corporation
from app.models.masters.panchayat import Panchayat
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.assets.wastetype import WasteType
from app.models.assets.bins import Bins

# Marker we reuse to find/refresh our own demo plan without colliding with real ones.
DEMO_TRIGGER_KG = 4242  # an obvious, unlikely-in-real-data sentinel


class SchedulerDemoSeeder(BaseSeeder):
    name = "scheduler_demo"

    def run(self):
        today = timezone.localdate()

        # ---- 1. Resolve prerequisites (reuse existing masters) -------------
        district = District.objects.filter(name="Erode", is_deleted=False).first()
        if not district:
            self.log("District 'Erode' not found — run the masters seeders first. Aborting.")
            return

        # Scope the demo plan to Erode Corporation so the scheduler demo also
        # exercises the corporation path (previously panchayat-only). The
        # panchayat below is still resolved only to locate real bin stops.
        corporation = Corporation.objects.filter(
            corporation_name="Erode Corporation", is_deleted=False
        ).first()
        if not corporation:
            self.log("Corporation 'Erode Corporation' not found — run CorporationSeeder first. Aborting.")
            return

        panchayat = (
            Panchayat.objects.filter(district_id=district, is_deleted=False)
            .order_by("panchayat_name")
            .first()
        )
        if not panchayat:
            self.log("No Panchayat under Erode — run PanchayatSeeder first. Aborting.")
            return

        template = (
            StaffTemplate.objects.filter(is_deleted=False, status=StaffTemplate.Status.ACTIVE)
            .order_by("created_at")
            .first()
        )
        if not template:
            self.log("No active StaffTemplate — run StaffTemplateSeeder first. Aborting.")
            return

        vehicle = VehicleCreation.objects.filter(is_deleted=False).order_by("vehicle_no").first()
        if not vehicle:
            self.log("No vehicle — run VehicleCreationSeeder first. Aborting.")
            return

        waste_type = WasteType.objects.filter(is_deleted=False).order_by("waste_type_name").first()
        if not waste_type:
            self.log("No WasteType — run WasteTypeSeeder first. Aborting.")
            return

        # ---- 2. Create / refresh the demo TripPlan -------------------------
        # Guaranteed-scheduled: ACTIVE + APPROVED + auto-assign + every weekday.
        plan, created = TripPlan.objects.update_or_create(
            district=district,
            corporation=corporation,
            panchayat=None,
            collection_type=TripPlan.COLLECTION_TYPE_BIN,
            trip_trigger_weight_kg=DEMO_TRIGGER_KG,  # our sentinel
            is_deleted=False,
            defaults={
                "state": corporation.state_id,
                "area_type": corporation.area_type_id,
                "staff_template_id": template,
                "vehicle_id": vehicle,
                "scheduled_time": time(7, 0),
                "max_vehicle_capacity_kg": 5000,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "status": TripPlan.Status.ACTIVE,
                "is_active": True,
                "is_auto_assign": True,
                "repeat_days": [0, 1, 2, 3, 4, 5, 6],  # runs every day
            },
        )
        plan.waste_types.set([waste_type])
        verb = "Created" if created else "Refreshed"
        self.log(f"{verb} demo TripPlan {plan.display_code} ({plan.unique_id}) on {corporation.corporation_name}.")

        # ---- 3. Give it real bin stops (so daily points are generated) -----
        cps = list(
            Collection_point.objects.filter(
                panchayat=panchayat, is_deleted=False, is_active=True
            ).order_by("cp_name")[:3]
        )
        if not cps:
            cps = list(
                Collection_point.objects.filter(
                    district=district, is_deleted=False, is_active=True
                ).order_by("cp_name")[:3]
            )
        if not cps:
            # Fall back to any collection points so the demo still produces stops.
            cps = list(Collection_point.objects.filter(is_deleted=False, is_active=True).order_by("cp_name")[:3])

        stop_count = 0
        for seq, cp in enumerate(cps, start=1):
            bin_obj = Bins.objects.filter(
                collection_point_id=cp, is_deleted=False, is_active=True
            ).first()
            TripPlanCollectionPoint.objects.update_or_create(
                trip_plan_id=plan,
                collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                collection_point_id=cp,
                defaults={
                    "bin_id": bin_obj,
                    "sequence": seq,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            stop_count += 1
        self.log(f"Demo plan has {stop_count} active stop(s).")

        # ---- 4. Clear today's generated data so the scheduler shows effect -
        # We HARD-clean only this demo plan's assignment for today, so a fresh
        # `generate_daily_trips` run visibly creates new records each time.
        existing_today = DailyTripAssignment.objects.filter(trip_plan_id=plan, trip_date=today)
        removed = existing_today.count()
        existing_today.delete()  # cascades to DailyTripCollectionPoint via FK
        if removed:
            self.log(f"Cleared {removed} existing assignment(s) for today so the scheduler can regenerate.")

        # ---- 5. Print the ready-to-run instructions ------------------------
        self.log("=" * 60)
        self.log("DEMO READY. Now run the job scheduler and watch it work:")
        self.log("  python manage.py generate_daily_trips")
        self.log("Then run it again — it should skip (no duplicates):")
        self.log("  python manage.py generate_daily_trips")
        self.log(f"Or trigger via API: POST /api/v1/schedule-masters/daily-trip-assignments/generate-daily/")
        self.log("=" * 60)
