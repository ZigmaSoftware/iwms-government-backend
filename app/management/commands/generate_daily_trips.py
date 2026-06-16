from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint


class Command(BaseCommand):
    help = "Generate DailyTripAssignment records from active TripPlan entries (auto-assign)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            help="Optional date (YYYY-MM-DD) to generate trips for. Defaults to today.",
            required=False,
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        if options.get("date"):
            try:
                today = timezone.datetime.strptime(options.get("date"), "%Y-%m-%d").date()
            except Exception as e:
                self.stderr.write(f"Invalid date: {e}")
                return

        weekday = today.weekday()  # Monday=0 .. Sunday=6

        plans = TripPlan.objects.filter(
            is_deleted=False,
            status=TripPlan.Status.ACTIVE,
            approval_status=TripPlan.ApprovalStatus.APPROVED,
            is_auto_assign=True,
        )

        created_count = 0
        skipped_count = 0
        for plan in plans.select_related("company_id", "project_id").all():
            repeat_days = plan.repeat_days or []
            if not repeat_days:
                # No repeat days configured; skip
                skipped_count += 1
                continue
            try:
                # ensure list of ints
                allowed = [int(d) for d in repeat_days]
            except Exception:
                self.stderr.write(f"TripPlan {plan.unique_id} has invalid repeat_days: {repeat_days}")
                skipped_count += 1
                continue

            if weekday not in allowed:
                skipped_count += 1
                continue

            defaults = {
                "staff_template_id": plan.staff_template_id,
                "vehicle_id": plan.vehicle_id,
                "waste_type_id": plan.waste_type_id,
                "panchayat_id": plan.panchayat_id,
                "ward_id": plan.ward_id,
                "scheduled_time": plan.scheduled_time,
            }

            with transaction.atomic():
                assignment, created = DailyTripAssignment.objects.get_or_create(
                    company_id=plan.company_id,
                    project_id=plan.project_id,
                    trip_plan_id=plan,
                    trip_date=today,
                    defaults=defaults,
                )

                if created:
                    created_count += 1
                    # create collection points
                    stops = (
                        TripPlanCollectionPoint.objects
                        .filter(trip_plan_id=plan, is_active=True, is_deleted=False)
                        .order_by("sequence")
                    )
                    cp_created = 0
                    for stop in stops:
                        cp_obj, cp_new = DailyTripCollectionPoint.objects.get_or_create(
                            trip_assignment_id=assignment,
                            collection_point_id=stop.collection_point_id,
                            defaults={
                                "bin_id": stop.bin_id,
                                "sequence": stop.sequence,
                                "status": DailyTripCollectionPoint.STATUS_PENDING,
                            },
                        )
                        if cp_new:
                            cp_created += 1
                    self.stdout.write(
                        f"Created assignment {assignment.unique_id} with {cp_created} collection points for plan {plan.unique_id}"
                    )
                else:
                    self.stdout.write(f"Assignment already exists for plan {plan.unique_id} on {today}")

        self.stdout.write(f"Finished. assignments_created={created_count} skipped={skipped_count}")
