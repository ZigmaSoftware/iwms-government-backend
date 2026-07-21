from datetime import timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.trip_attendance import TripAttendance


class TripAttendanceSeeder(BaseSeeder):
    name = "trip_attendance"

    def run(self):
        trip = DailyTripAssignment.objects.order_by("-created_at").first()
        if not trip:
            self.log("TripAttendanceSeeder skipped (no daily trip assignments).")
            return

        if trip.status != DailyTripAssignment.STATUS_IN_PROGRESS:
            trip.status = DailyTripAssignment.STATUS_IN_PROGRESS
            trip.save(update_fields=["status"])

        staff_template = trip.staff_template_id
        if not staff_template:
            self.log("TripAttendanceSeeder skipped (missing staff template).")
            return

        staff_members = [
            staff_template.operator_id,
            staff_template.driver_id,
        ]

        created = 0
        for idx, staff in enumerate(staff_members):
            if not staff:
                continue

            attendance_time = timezone.now() - timedelta(minutes=50 + (idx * 10))
            _, was_created = TripAttendance.objects.get_or_create(
                daily_trip_assignment=trip,
                staff=staff,
                vehicle=trip.vehicle_id,
                attendance_time=attendance_time,
                defaults={
                    "latitude": "13.0826800",
                    "longitude": "80.2707180",
                    "source": TripAttendance.Source.MOBILE,
                },
            )
            if was_created:
                created += 1

        self.log(f"---Trip attendance seeded | Created: {created}---")
