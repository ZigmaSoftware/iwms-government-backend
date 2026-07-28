from datetime import timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.trip_attendance import TripAttendance


class TripAttendanceSeeder(BaseSeeder):
    """One attendance row per driver/operator on the most recent assignment
    in each operational district. Bug fix: the old seeder hardcoded Chennai
    coordinates for every attendance regardless of the trip's real district
    — this version uses that district's own real coordinates instead."""

    name = "trip_attendance"

    def run(self):
        created = 0
        for district_name in DISTRICTS:
            trip = (
                DailyTripAssignment.objects.filter(district__name=district_name)
                .order_by("-trip_date", "-created_at")
                .select_related("district", "staff_template_id", "vehicle_id")
                .first()
            )
            if not trip:
                self.log(f"No daily trip assignment for '{district_name}' — skipping.")
                continue

            if trip.status != DailyTripAssignment.STATUS_IN_PROGRESS:
                trip.status = DailyTripAssignment.STATUS_IN_PROGRESS
                trip.save(update_fields=["status"])

            staff_template = trip.staff_template_id
            if not staff_template:
                self.log(f"'{district_name}' trip missing staff template — skipping.")
                continue

            lat, lon = 11.0, 78.0
            if trip.district and trip.district.coordinates:
                point = trip.district.coordinates[0]
                lat, lon = point["latitude"], point["longitude"]

            for idx, staff in enumerate([staff_template.operator_id, staff_template.driver_id]):
                if not staff:
                    continue
                attendance_time = timezone.now() - timedelta(minutes=50 + (idx * 10))
                _, was_created = TripAttendance.objects.get_or_create(
                    daily_trip_assignment=trip,
                    staff=staff,
                    vehicle=trip.vehicle_id,
                    attendance_time=attendance_time,
                    defaults={
                        "latitude": f"{lat:.7f}",
                        "longitude": f"{lon:.7f}",
                        "source": TripAttendance.Source.MOBILE,
                    },
                )
                if was_created:
                    created += 1

        self.log(f"---Trip attendance seeded | Created: {created}---")
