from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

TARGET = 15

# Simulate realistic GPS coordinates (Chennai area)
GPS_SAMPLES = [
    (13.083000, 80.271000),
    (13.090000, 80.265000),
    (13.077000, 80.280000),
    (13.085000, 80.258000),
    (13.095000, 80.273000),
    (13.070000, 80.290000),
    (13.100000, 80.261000),
    (13.080000, 80.275000),
    (13.088000, 80.268000),
    (13.075000, 80.285000),
    (13.093000, 80.262000),
    (13.082000, 80.278000),
    (13.097000, 80.256000),
    (13.073000, 80.287000),
    (13.086000, 80.270000),
]


class BinCollectionEventSeeder(BaseSeeder):
    name = "bin_collection_event"

    def run(self):
        company = Company.objects.filter(name="IWMS").first()
        project = (
            Project.objects.filter(name=f"{company.name} Main Project").first()
            if company else None
        )

        if not company or not project:
            self.log("Company/Project not found — skipping.")
            return

        # Fetch DailyTripCollectionPoints that don't yet have a BinCollectionEvent.
        # Order by assignment date descending so we seed from the most recent trips.
        trip_cps = (
            DailyTripCollectionPoint.objects
            .filter(
                trip_assignment_id__company_id=company,
                trip_assignment_id__project_id=project,
                is_deleted=False,
            )
            .exclude(
                # Skip any DTCP that already has a BCE (OneToOneField enforces uniqueness)
                unique_id__in=BinCollectionEvent.objects.values_list(
                    "trip_collection_point_id", flat=True
                )
            )
            .exclude(trip_assignment_id__status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related(
                "trip_assignment_id",
                "trip_assignment_id__company_id",
                "trip_assignment_id__project_id",
                "trip_assignment_id__panchayat_id",
                "trip_assignment_id__ward_id",
                "trip_assignment_id__vehicle_id",
                "collection_point_id",
                "bin_id",
                "bin_id__wastetype_id",
            )
            .order_by("-trip_assignment_id__trip_date", "sequence")
        )

        available = list(trip_cps[:TARGET])

        if not available:
            self.log("No eligible DailyTripCollectionPoints found — skipping.")
            return

        created_count = 0
        backfilled_count = 0

        # Backfill: mark any DTCP as collected if a BCE already exists for it
        orphan_tcps = (
            DailyTripCollectionPoint.objects
            .filter(
                company_id=company,
                project_id=project,
                is_collected=False,
                is_deleted=False,
            )
            .select_related("bin_id")
        )
        for tcp in orphan_tcps:
            bce = BinCollectionEvent.objects.filter(
                trip_collection_point_id=tcp
            ).first()
            if bce:
                tcp.mark_collected(
                    weight_kg=float(bce.collected_weight_kg),
                    collected_by=None,
                )
                backfilled_count += 1

        for i, trip_cp in enumerate(available):
            if not trip_cp.bin_id:
                continue

            assignment = trip_cp.trip_assignment_id
            bin_obj = trip_cp.bin_id
            weight_kg = round(float(bin_obj.bin_capacity or 240) * 0.65, 2)
            lat, lng = GPS_SAMPLES[i % len(GPS_SAMPLES)]

            BinCollectionEvent.objects.create(
                company_id=company,
                project_id=project,
                trip_assignment_id=assignment,
                trip_collection_point_id=trip_cp,
                collection_point_id=trip_cp.collection_point_id,
                bin_id=bin_obj,
                waste_type_id=getattr(bin_obj, "wastetype_id", None),
                vehicle_id=getattr(assignment, "vehicle_id", None),
                panchayat_id=assignment.panchayat_id,
                collected_weight_kg=weight_kg,
                driver_latitude=lat,
                driver_longitude=lng,
                notes="Seeded sample scan event",
            )

            if not trip_cp.is_collected:
                trip_cp.mark_collected(weight_kg=weight_kg, collected_by=None)

            created_count += 1

        self.log(
            f"---BinCollectionEvent seeded | created={created_count} | backfilled={backfilled_count}---"
        )
