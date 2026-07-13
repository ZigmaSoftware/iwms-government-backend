import math
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.role_assigns.userType import UserType
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.hierarchy import copy_flat_geo


class DriverUserSeeder(BaseSeeder):
    """Create a ready-to-login mobile driver (`driver_user` / `Driver123`) wired
    to a real daily trip so the app's bin AND household QR-scan flows work.

    The stock staff seeders leave user_type/role/geo unset, so none of them can
    actually log in through the mobile `login/` endpoint. This seeder produces a
    fully-formed driver and, without disturbing the trip's collection points,
    - makes it the driver on an existing today assignment (reuses its bin CPs), and
    - adds household stops (customer-linked) for the same panchayat.
    """

    name = "DriverUserSeeder"

    USERNAME = "driver_user"
    PASSWORD = "Driver123"

    # Demo trip collection points: how many, and where/how far they spread.
    NUM_COLLECTION_POINTS = 8
    TRIP_CENTER = (11.3805, 77.7032)  # Modakkurichi panchayat area
    TRIP_RADIUS_KM = 1.0

    def run(self):
        user_type = UserType.objects.filter(name__iexact="government").first()
        driver_role = GovernmentStaffUserType.objects.filter(
            name="govt_panchayat_driver"
        ).first()
        if not user_type or not driver_role:
            self.log("Government UserType / govt_panchayat_driver role missing — skipping.")
            return

        # 1. Create / update the driver login (geo stamped once the trip is chosen).
        driver, created = Staffcreation.objects.get_or_create(
            username=self.USERNAME,
            defaults={
                "employee_name": "Driver User",
                "password": make_password(self.PASSWORD),
                "user_type_id": user_type,
                "governmentusertype_id": driver_role,
                "is_active": True,
                "is_deleted": False,
                "is_superuser": False,
                "login_enabled": True,
            },
        )
        if not created:
            driver.employee_name = "Driver User"
            driver.password = make_password(self.PASSWORD)
            driver.user_type_id = user_type
            driver.governmentusertype_id = driver_role
            driver.staffusertype_id = None
            driver.is_active = True
            driver.is_deleted = False
            driver.is_superuser = False
            driver.login_enabled = True
            driver.save()

        # Pick TODAY's trip (assignments are per-day, so this must target today).
        # Prefer one already on driver_user's template — that's the exact trip
        # `my-trip-today` will resolve — otherwise claim the first available.
        today = timezone.localdate()
        base = (
            DailyTripAssignment.objects
            .filter(trip_date=today, is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
        )
        assignment = (
            base.filter(staff_template_id__driver_id=driver).order_by("unique_id").first()
            or base.order_by("unique_id").first()
        )
        if not assignment:
            self.log("No daily trip assignment for today — run schedule seeders first.")
            return

        # Hierarchy: stamp the driver with the trip's geography.
        copy_flat_geo(driver, assignment)
        driver.save()
        self.log(f"{'Created' if created else 'Updated'} driver login: {self.USERNAME} / {self.PASSWORD}")

        # 2. Make driver_user the driver on the trip's staff template
        #    (reuses the assignment's existing bin collection points).
        template = assignment.staff_template_id
        if template is None:
            self.log("Assignment has no staff template — cannot wire driver.")
            return
        template.driver_id = driver
        template.save(update_fields=["driver_id", "updated_at"])
        self.log(f"Assigned {self.USERNAME} as driver on {template.unique_id} ({assignment.unique_id}).")

        # 2b. driver_user collects WET (Organic) waste. Make every assignment on this
        #     template Organic, then rebuild the ACTIVE trip's collection points as
        #     dedicated Organic bins INSIDE the trip's own panchayat — the stock seed
        #     shares CPs across panchayats, so scans would otherwise fail the
        #     waste-type / panchayat checks. This keeps the trip hierarchy-consistent.
        today = timezone.localdate()
        wet_waste = WasteType.objects.filter(
            waste_type_name__iexact="Organic Waste"
        ).first()
        if wet_waste:
            DailyTripAssignment.objects.filter(
                staff_template_id=template, trip_date=today, is_deleted=False
            ).update(waste_type_id=wet_waste)
            assignment.refresh_from_db()

            # Rebuild the active trip fresh: clear any prior scan events, stale
            # (possibly verified) trip log, and existing collection points.
            BinCollectionEvent.objects.filter(trip_assignment_id=assignment).delete()
            DailyTripLog.objects.filter(trip_assignment_id=assignment).delete()
            DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment
            ).delete()
            # Reset to a fresh, workable trip. Other seeders (e.g. the supervisor
            # month-data seeder) may have completed/logged this assignment; the
            # driver must start today's demo trip from Scheduled with nothing
            # collected yet.
            assignment.status = DailyTripAssignment.STATUS_SCHEDULED
            assignment.approval_status = DailyTripAssignment.APPROVAL_APPROVED
            assignment.actual_start_time = None
            assignment.actual_end_time = None
            assignment.save(
                update_fields=[
                    "status",
                    "approval_status",
                    "actual_start_time",
                    "actual_end_time",
                    "updated_at",
                ]
            )
            # Spread the collection points across ~1 km around the trip centre so
            # they render as distinct stops on the map (not stacked on one pin).
            center_lat, center_lng = self.TRIP_CENTER
            for seq in range(1, self.NUM_COLLECTION_POINTS + 1):
                angle = (2 * math.pi / self.NUM_COLLECTION_POINTS) * (seq - 1)
                # Vary the radius (0.25–1.0 km) so points sit at different rings.
                radius_km = self.TRIP_RADIUS_KM * (0.25 + 0.75 * ((seq - 1) % 4) / 3.0)
                d_lat = (radius_km / 111.0) * math.cos(angle)
                d_lng = (
                    radius_km / (111.0 * math.cos(math.radians(center_lat)))
                ) * math.sin(angle)
                lat = Decimal(str(round(center_lat + d_lat, 6)))
                lng = Decimal(str(round(center_lng + d_lng, 6)))
                cp = Collection_point.objects.create(
                    state=assignment.state,
                    district=assignment.district,
                    area_type=assignment.area_type,
                    panchayat=assignment.panchayat,
                    cp_name=f"Wet Waste Point {seq} (driver_user)",
                    latitude=lat,
                    longitude=lng,
                    is_active=True,
                    is_deleted=False,
                )
                bin_obj = Bins.objects.create(
                    collection_point_id=cp,
                    wastetype_id=wet_waste,
                    bin_name=f"Wet Waste Bin {seq} (driver_user)",
                    bin_capacity=120,
                    bin_type="large",
                    bin_image="",
                    is_active=True,
                    is_deleted=False,
                )
                DailyTripCollectionPoint.objects.create(
                    trip_assignment_id=assignment,
                    collection_point_id=cp,
                    bin_id=bin_obj,
                    sequence=seq,
                    is_collected=False,
                    status=DailyTripCollectionPoint.STATUS_PENDING,
                    is_active=True,
                    is_deleted=False,
                )
            self.log(
                f"Rebuilt {assignment.unique_id} with {self.NUM_COLLECTION_POINTS} "
                f"Organic bins spread within {self.TRIP_RADIUS_KM:g} km of its panchayat."
            )

        # 3. Add household stops (customer-linked) for the trip's panchayat so the
        #    household QR-scan / mark-status flow has data — hierarchy-consistent.
        customers = list(
            CustomerCreation.objects.filter(
                panchayat_id=assignment.panchayat_id,
                is_deleted=False,
                is_active=True,
            )
        )
        if not customers:
            # Fall back to any active customers so the flow is still exercisable.
            customers = list(
                CustomerCreation.objects.filter(is_deleted=False, is_active=True)[:3]
            )

        existing_seq = [
            h.sequence
            for h in DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment)
        ]
        seq = (max(existing_seq) + 1) if existing_seq else 1
        household_count = 0
        for customer in customers:
            _, made = DailyTripHouseholdCollection.objects.get_or_create(
                trip_assignment_id=assignment,
                customer_id=customer,
                collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD,
                defaults={
                    "sequence": seq,
                    "status": DailyTripHouseholdCollection.STATUS_PENDING,
                    "is_collected": False,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if made:
                seq += 1
                household_count += 1

        self.log(
            f"---driver_user wired: assignment={assignment.unique_id}, "
            f"household stops added={household_count}---"
        )
