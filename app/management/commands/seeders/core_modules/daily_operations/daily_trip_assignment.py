from datetime import datetime, time, timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.trip_plan import TripPlan

# Reserved for the live driver_user/scheduler-demo trip — history only ever
# covers yesterday back HISTORY_DAYS days, never today. Kept small since
# this is the single biggest multiplier on total seed volume/runtime (every
# trip plan gets this many daily assignments, each cascading into bin/waste
# events and an auto-generated DailyTripLog).
HISTORY_DAYS = 4

FLAT_GEO_FIELDS = (
    "state", "district", "area_type", "corporation",
    "municipality", "town_panchayat", "panchayat_union", "panchayat",
)

# driver_user.py/supervisor_user.py own and continuously reset their
# dedicated demo trip plans' "today" assignment — the generic 7-day history
# walk here must not also backfill history for those plans, or driver_user's
# demo route ends up with a mix of hand-curated live data and generic
# history that grows once (the day after DriverUserSeeder first creates its
# plan) and never converges.
DEMO_STAFF_USERNAMES = {"driver_user", "operator_user"}


def _deterministic_start_and_duration(scheduled_time, day_offset):
    """Index-derived (not random) start offset + duration so history stays
    byte-identical across re-runs. Duration (rather than a second absolute
    time-of-day) is what actually gets added to the start timestamp, so the
    end is always after the start even when the start wraps past midnight."""
    start_minutes = scheduled_time.hour * 60 + scheduled_time.minute + 5 + (day_offset % 4) * 3
    duration_minutes = 180 + (day_offset % 5) * 7
    start = time((start_minutes // 60) % 24, start_minutes % 60)
    return start, duration_minutes


class DailyTripAssignmentSeeder(BaseSeeder):
    """7 days of history (today-1 .. today-7) across every active/approved
    TripPlan in each operational district. Keyed on (trip_plan, trip_date)
    so re-running `manage.py seed` any number of times converges to the
    same fixed set of rows — no unbounded growth like the old TARGET=15
    walk-back-and-create pattern."""

    name = "daily_trip_assignment"

    def run(self):
        today = timezone.localdate()

        plans = list(
            TripPlan.objects.filter(
                is_deleted=False,
                status=TripPlan.Status.ACTIVE,
                approval_status=TripPlan.ApprovalStatus.APPROVED,
            )
            .exclude(staff_template_id__driver_id__username__in=DEMO_STAFF_USERNAMES)
            .select_related("staff_template_id", "vehicle_id", "district")
            .prefetch_related("waste_types")
        )

        created_count = 0
        skipped_incomplete = 0
        for plan in plans:
            if not plan.district_id:
                continue
            template = plan.staff_template_id
            if not template or not template.driver_id_id or not template.operator_id_id or not plan.vehicle_id_id:
                skipped_incomplete += 1
                continue

            alt_template = template.alternative_templates.first()

            for day_offset in range(1, HISTORY_DAYS + 1):
                trip_date = today - timedelta(days=day_offset)

                assignment, created = DailyTripAssignment.objects.get_or_create(
                    trip_plan_id=plan,
                    trip_date=trip_date,
                    defaults={
                        "staff_template_id": template,
                        "vehicle_id": plan.vehicle_id,
                        **{field: getattr(plan, field, None) for field in FLAT_GEO_FIELDS},
                        "scheduled_time": plan.scheduled_time,
                        "status": DailyTripAssignment.STATUS_SCHEDULED,
                        "approval_status": DailyTripAssignment.APPROVAL_APPROVED,
                    },
                )
                assignment.waste_types.set(plan.waste_types.all())
                assignment.wards.set(plan.wards.all())

                # Keep existing history aligned when the Trip Plan seeder
                # changes a plan to a shared staff-template/vehicle pair.
                expected_values = {
                    "staff_template_id": template,
                    "vehicle_id": plan.vehicle_id,
                    **{
                        field: getattr(plan, field, None)
                        for field in FLAT_GEO_FIELDS
                    },
                    "scheduled_time": plan.scheduled_time,
                }
                update_fields = []
                for field, value in expected_values.items():
                    if getattr(assignment, field) != value:
                        setattr(assignment, field, value)
                        update_fields.append(field)

                if created:
                    created_count += 1

                if day_offset == 3 and alt_template and not assignment.alt_staff_template_id_id:
                    assignment.alt_staff_template_id = alt_template
                    update_fields.append("alt_staff_template_id")

                # Deliberately NOT mark_started()/mark_ended(): those guard
                # against acting on an already-Completed trip (correct for a
                # live transition, wrong here) — a row a previous run of this
                # seeder already force-set to Completed via raw field
                # assignment would then have mark_started() no-op forever,
                # permanently stuck with a null actual_start_at/actual_end_at.
                # A seeder needs "ensure this state", so stamp both the
                # authoritative `_at` fields and their legacy TimeField
                # mirrors directly whenever they don't already match.
                start_time, duration_minutes = _deterministic_start_and_duration(plan.scheduled_time, day_offset)
                started_at = timezone.make_aware(datetime.combine(trip_date, start_time))
                ended_at = started_at + timedelta(minutes=duration_minutes)
                if assignment.actual_start_at != started_at:
                    assignment.actual_start_at = started_at
                    assignment.actual_start_time = timezone.localtime(started_at).time()
                    update_fields += ["actual_start_at", "actual_start_time"]
                if assignment.actual_end_at != ended_at:
                    assignment.actual_end_at = ended_at
                    assignment.actual_end_time = timezone.localtime(ended_at).time()
                    update_fields += ["actual_end_at", "actual_end_time"]
                if assignment.status == DailyTripAssignment.STATUS_SCHEDULED:
                    assignment.status = DailyTripAssignment.STATUS_COMPLETED
                    update_fields.append("status")

                if update_fields:
                    assignment.save(update_fields=[*update_fields, "updated_at"])

        self.log(
            f"---DailyTripAssignment seeded | created={created_count} | "
            f"skipped (incomplete staff/vehicle)={skipped_incomplete}---"
        )
