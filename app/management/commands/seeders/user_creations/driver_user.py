import math
from datetime import time
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.db.models import Count, Q
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.secondary_bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.role_assigns.userType import UserType
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.secondary_bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import (
    Staffcreation,
    StaffcreationOfficeDetails,
)
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.hierarchy import copy_flat_geo, sync_staff_data_scope


class DriverUserSeeder(BaseSeeder):
    """Wire a ready-to-login mobile driver + operator to a REAL trip built the
    proper way, so the app's bin AND household flows work end-to-end.

    Instead of hijacking a pre-existing assignment (the old behaviour), this
    seeder builds the whole chain the domain expects:

        StaffTemplate(driver_user, operator_user)
          -> TripPlan (bin_collection)      -> TripPlanCollectionPoint (bins)
          -> TripPlan (household_collection) -> TripPlanCollectionPoint (area)
          -> DailyTripAssignment (generated per plan for today)
               -> DailyTripCollectionPoint  (auto, via post_save signal)
               -> DailyTripHouseholdCollection (auto, via post_save signal)

    driver_user collects Organic (wet) waste. The bin trip is generated first so
    it wins the app's lowest-unique_id resolution (my-trip-today / scan-bin);
    the household trip drives the customer QR / finalize flow.
    """

    name = "DriverUserSeeder"

    USERNAME = "driver_user"
    PASSWORD = "Driver123"
    DRIVER_ROLE = "govt_panchayat_driver"

    OPERATOR_USERNAME = "operator_user"
    OPERATOR_PASSWORD = "Operator123"
    OPERATOR_ROLE = "govt_panchayat_operator"

    WASTE_TYPE_NAME = "Organic Waste"

    # Demo bin stops: how many, and where/how far they spread (map cosmetics only
    # — scan validation compares panchayat, not coordinates).
    NUM_COLLECTION_POINTS = 8
    TRIP_CENTER = (11.3805, 77.7032)  # Modakkurichi panchayat area
    TRIP_RADIUS_KM = 1.0
    SCHEDULED_TIME = time(6, 30)

    # ------------------------------------------------------------------
    def run(self):
        user_type = UserType.objects.filter(name__iexact="government").first()
        if not user_type:
            self.log("Government UserType missing — skipping.")
            return

        driver_role = GovernmentStaffUserType.objects.filter(
            name=self.DRIVER_ROLE
        ).first()
        if not driver_role:
            self.log(f"Role '{self.DRIVER_ROLE}' missing — skipping.")
            return
        operator_role, _ = GovernmentStaffUserType.objects.get_or_create(
            name=self.OPERATOR_ROLE,
            usertype_id=user_type,
            defaults={"level": "panchayat", "is_active": True, "is_deleted": False},
        )

        wet_waste = WasteType.objects.filter(
            waste_type_name__iexact=self.WASTE_TYPE_NAME
        ).first()
        if not wet_waste:
            self.log(f"WasteType '{self.WASTE_TYPE_NAME}' missing — skipping.")
            return

        vehicle = (
            VehicleCreation.objects.filter(is_deleted=False)
            .order_by("vehicle_no")
            .first()
        )
        if not vehicle:
            self.log("No vehicle found — run VehicleCreationSeeder first. Skipping.")
            return

        panchayat = self._pick_demo_panchayat()
        if not panchayat:
            self.log("No panchayat available — skipping.")
            return

        # 1. Logins ----------------------------------------------------
        driver = self._upsert_staff(
            self.USERNAME, "Driver User", self.PASSWORD, user_type, driver_role
        )
        operator = self._upsert_staff(
            self.OPERATOR_USERNAME, "Operator User", self.OPERATOR_PASSWORD,
            user_type, operator_role,
        )

        # 2. Dedicated staff template (driver_user + operator_user) -----
        template = self._get_or_create_template(driver, operator, panchayat)

        # 2b. Un-hijack: strip driver_user / operator_user out of any OTHER
        #     template a previous run polluted, so the app only resolves the
        #     trips this seeder builds.
        self._detach_from_foreign_templates(driver, operator, keep=template)

        # 3. Organic bins + collection points inside the demo panchayat -
        bins = self._ensure_bins(panchayat, wet_waste)

        # 4. Trip plans (bin + household) sharing the template ----------
        bin_plan = self._get_or_create_plan(
            TripPlan.COLLECTION_TYPE_BIN, template, vehicle, panchayat, wet_waste
        )
        self._sync_bin_stops(bin_plan, bins)

        household_plan = self._get_or_create_plan(
            TripPlan.COLLECTION_TYPE_HOUSEHOLD, template, vehicle, panchayat, wet_waste
        )
        self._sync_household_stop(household_plan)

        # 5. Generate today's assignments — BIN FIRST (lower unique_id so the
        #    app resolves the bin trip for my-trip-today / scan-bin). Signals
        #    build the daily collection points + household collections.
        today = timezone.localdate()
        bin_assignment = self._generate_assignment(bin_plan, today)
        household_assignment = self._generate_assignment(household_plan, today)

        # 6. Fresh demo state + data scope ------------------------------
        self._reset_bin_assignment(bin_assignment)
        self._reset_household_assignment(household_assignment)

        copy_flat_geo(driver, bin_assignment)
        driver.save()
        copy_flat_geo(operator, bin_assignment)
        operator.save()
        sync_staff_data_scope(driver, bin_assignment)
        sync_staff_data_scope(operator, bin_assignment)

        # 7. Guarantee the app resolves driver_user's OWN clean trip. The mobile
        #    resolver picks the lowest-unique_id trip where the user is driver/
        #    operator; any stale/contaminated trip (e.g. an older hijacked
        #    assignment whose bins are a different waste type) could otherwise win
        #    and show "this bin is X; your trip collects Organic". Heal it.
        self._ensure_clean_resolution(
            driver, operator,
            {bin_assignment.unique_id, household_assignment.unique_id},
        )

        bin_cp_count = DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=bin_assignment, is_deleted=False
        ).count()
        hh_count = DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=household_assignment, is_deleted=False
        ).count()
        self.log(
            f"---driver_user wired properly | template={template.display_code} "
            f"(driver={self.USERNAME}, operator={self.OPERATOR_USERNAME}) | "
            f"panchayat={panchayat.panchayat_name} | "
            f"bin trip={bin_assignment.unique_id} ({bin_cp_count} bins) | "
            f"household trip={household_assignment.unique_id} ({hh_count} stops)---"
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _upsert_staff(self, username, name, password, user_type, role):
        staff, created = Staffcreation.objects.get_or_create(
            username=username,
            defaults={
                "employee_name": name,
                "password": make_password(password),
                "user_type_id": user_type,
                "governmentusertype_id": role,
                "is_active": True,
                "is_deleted": False,
                "is_superuser": False,
                "login_enabled": True,
            },
        )
        if not created:
            staff.employee_name = name
            staff.password = make_password(password)
            staff.user_type_id = user_type
            staff.governmentusertype_id = role
            staff.staffusertype_id = None
            staff.is_active = True
            staff.is_deleted = False
            staff.is_superuser = False
            staff.login_enabled = True
            staff.save()
        self.log(
            f"{'Created' if created else 'Updated'} login: {username} / {password}"
        )
        return staff

    def _pick_demo_panchayat(self):
        """Prefer a panchayat that actually has active customers so the
        household fan-out has stops; fall back to any active panchayat."""
        with_customers = (
            CustomerCreation.objects.filter(is_deleted=False, is_active=True)
            .exclude(panchayat_id__isnull=True)
            .values("panchayat_id")
            .annotate(n=Count("unique_id"))
            .order_by("-n")
        )
        for row in with_customers:
            panchayat = Panchayat.objects.filter(
                unique_id=row["panchayat_id"], is_deleted=False, is_active=True
            ).first()
            if panchayat:
                return panchayat
        return Panchayat.objects.filter(
            is_deleted=False, is_active=True
        ).order_by("unique_id").first()

    def _get_or_create_template(self, driver, operator, panchayat):
        template = StaffTemplate.objects.filter(
            driver_id=driver, operator_id=operator, is_deleted=False
        ).first()
        if template is None:
            template = StaffTemplate.objects.create(
                driver_id=driver,
                operator_id=operator,
                state=panchayat.state_id,
                district=panchayat.district_id,
                area_type=panchayat.area_type_id,
                panchayat=panchayat,
                approval_status=StaffTemplate.ApprovalStatus.APPROVED,
                status=StaffTemplate.Status.ACTIVE,
                is_active=True,
                is_deleted=False,
            )
        else:
            template.state = panchayat.state_id
            template.district = panchayat.district_id
            template.area_type = panchayat.area_type_id
            template.panchayat = panchayat
            template.approval_status = StaffTemplate.ApprovalStatus.APPROVED
            template.status = StaffTemplate.Status.ACTIVE
            template.is_active = True
            template.is_deleted = False
            template.save()
        return template

    def _fallback_staff(self, demo_ids):
        """Two office-staff to stand in as driver/operator on templates we strip
        the demo users out of. Returns (None, None) if none exist."""
        fb = list(
            StaffcreationOfficeDetails.objects.filter(is_deleted=False)
            .exclude(staff_unique_id__in=demo_ids)
            .order_by("staff_unique_id")[:2]
        )
        if not fb:
            return (None, None)
        return (fb[0], fb[1] if len(fb) > 1 else fb[0])

    def _detach_from_foreign_templates(self, driver, operator, keep):
        """A previous (hijacking) run may have set driver_user/operator_user as
        the driver, operator, or an extra operator on templates that aren't
        ours. Reassign/strip those so the app resolves only this seeder's
        trips."""
        demo_ids = {driver.staff_unique_id, operator.staff_unique_id}
        fb_driver, fb_operator = self._fallback_staff(demo_ids)
        if fb_driver is None:
            return

        # Templates where a demo user is the driver or operator...
        foreign = (
            StaffTemplate.objects
            .exclude(pk=keep.pk)
            .filter(Q(driver_id__in=demo_ids) | Q(operator_id__in=demo_ids))
        )
        fixed = 0
        for tmpl in foreign:
            if self._strip_demo_users(tmpl, demo_ids, fb_driver, fb_operator):
                fixed += 1

        # ...and templates that merely list a demo user in extra_operator_id
        # (JSON list — not covered by the FK filter above).
        for tmpl in StaffTemplate.objects.exclude(pk=keep.pk):
            extras = tmpl.extra_operator_id or []
            if demo_ids & set(extras):
                if self._strip_demo_users(tmpl, demo_ids, fb_driver, fb_operator):
                    fixed += 1
        if fixed:
            self.log(f"Detached demo users from {fixed} foreign staff template(s).")

    def _strip_demo_users(self, tmpl, demo_ids, fb_driver, fb_operator):
        """Remove the demo users from a single template (driver/operator FKs and
        the extra_operator_id list). Returns True if anything changed."""
        changed = False
        if tmpl.driver_id_id in demo_ids:
            tmpl.driver_id = fb_driver
            changed = True
        if tmpl.operator_id_id in demo_ids:
            tmpl.operator_id = fb_operator
            changed = True
        extras = tmpl.extra_operator_id or []
        kept = [e for e in extras if e not in demo_ids]
        if kept != extras:
            tmpl.extra_operator_id = kept
            changed = True
        if changed:
            tmpl.save(update_fields=[
                "driver_id", "operator_id", "extra_operator_id", "updated_at"
            ])
        return changed

    def _bins_match_waste_type(self, assignment):
        """True if every collection point on the assignment carries a bin of the
        assignment's own waste type (what the scan flow validates)."""
        cps = DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment, is_deleted=False
        ).select_related("bin_id")
        for cp in cps:
            if cp.bin_id_id and str(
                getattr(cp.bin_id, "wastetype_id_id", None)
            ) != str(assignment.waste_type_id_id):
                return False
        return True

    def _ensure_clean_resolution(self, driver, operator, own_ids):
        """Keep neutralizing whatever trip the app resolves for driver_user until
        it lands on one of driver_user's OWN trips with matching bins. Guards the
        driver's own trips so they are never neutralized."""
        from app.viewsets.operator_mobile.helpers import (
            OperatorFlowError,
            find_active_assignment_for_operator,
        )

        demo_ids = {driver.staff_unique_id, operator.staff_unique_id}
        fb_driver, fb_operator = self._fallback_staff(demo_ids)

        for _ in range(30):
            try:
                resolved = find_active_assignment_for_operator(driver)
            except OperatorFlowError:
                return  # no trip resolves — nothing to heal
            if resolved.unique_id in own_ids:
                if not self._bins_match_waste_type(resolved):
                    self.log(
                        f"WARNING: driver_user's own trip {resolved.unique_id} has "
                        f"bins that do not match its waste type — check _ensure_bins."
                    )
                return  # resolves the driver's own trip — done
            # A foreign/contaminated trip is resolved ahead of the driver's own.
            self._neutralize_foreign_assignment(
                resolved, demo_ids, fb_driver, fb_operator
            )
            self.log(
                f"Healed resolution: neutralized foreign trip {resolved.unique_id} "
                f"so driver_user resolves its own trip."
            )
        self.log("WARNING: driver_user resolution did not converge after 30 heals.")

    def _neutralize_foreign_assignment(self, assignment, demo_ids, fb_driver, fb_operator):
        tmpl = assignment.staff_template_id
        changed = False
        if tmpl is not None and fb_driver is not None:
            changed = self._strip_demo_users(tmpl, demo_ids, fb_driver, fb_operator)
        if not changed:
            # Its template no longer references a demo user (or no fallback
            # exists), yet it still resolves — cancel it so the resolver skips it.
            assignment.status = DailyTripAssignment.STATUS_CANCELLED
            assignment.save(update_fields=["status", "updated_at"])

    def _ensure_bins(self, panchayat, wet_waste):
        """Create/refresh NUM_COLLECTION_POINTS Organic bins in the panchayat.
        Idempotent: reuses collection points/bins by name across re-runs (they
        are PROTECT-referenced by trip stops, so never deleted)."""
        center_lat, center_lng = self.TRIP_CENTER
        bins = []
        for seq in range(1, self.NUM_COLLECTION_POINTS + 1):
            angle = (2 * math.pi / self.NUM_COLLECTION_POINTS) * (seq - 1)
            radius_km = self.TRIP_RADIUS_KM * (0.25 + 0.75 * ((seq - 1) % 4) / 3.0)
            d_lat = (radius_km / 111.0) * math.cos(angle)
            d_lng = (
                radius_km / (111.0 * math.cos(math.radians(center_lat)))
            ) * math.sin(angle)
            lat = Decimal(str(round(center_lat + d_lat, 6)))
            lng = Decimal(str(round(center_lng + d_lng, 6)))

            cp_name = f"Wet Waste Point {seq} (driver_user)"
            cp = Collection_point.objects.filter(
                cp_name=cp_name, panchayat=panchayat
            ).first()
            if cp is None:
                cp = Collection_point.objects.create(
                    state=panchayat.state_id,
                    district=panchayat.district_id,
                    area_type=panchayat.area_type_id,
                    panchayat=panchayat,
                    cp_name=cp_name,
                    latitude=lat,
                    longitude=lng,
                    is_active=True,
                    is_deleted=False,
                )
            else:
                cp.latitude = lat
                cp.longitude = lng
                cp.is_active = True
                cp.is_deleted = False
                cp.save(update_fields=[
                    "latitude", "longitude", "is_active", "is_deleted", "updated_at"
                ])

            bin_obj = Bins.objects.filter(
                collection_point_id=cp, wastetype_id=wet_waste
            ).first()
            if bin_obj is None:
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
            else:
                bin_obj.is_active = True
                bin_obj.is_deleted = False
                bin_obj.save(update_fields=["is_active", "is_deleted", "updated_at"])
            bins.append((cp, bin_obj))
        return bins

    def _get_or_create_plan(self, collection_type, template, vehicle, panchayat, wet_waste):
        plan, _ = TripPlan.objects.update_or_create(
            staff_template_id=template,
            collection_type=collection_type,
            panchayat=panchayat,
            is_deleted=False,
            defaults={
                "waste_type_id": wet_waste,
                "state": panchayat.state_id,
                "district": panchayat.district_id,
                "area_type": panchayat.area_type_id,
                "vehicle_id": vehicle,
                "scheduled_time": self.SCHEDULED_TIME,
                "trip_trigger_weight_kg": 100,
                "max_vehicle_capacity_kg": 5000,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "status": TripPlan.Status.ACTIVE,
                "is_active": True,
                "is_deleted": False,
                "is_auto_assign": True,
                "repeat_days": [0, 1, 2, 3, 4, 5, 6],
            },
        )
        plan.waste_types.set([wet_waste])
        return plan

    def _sync_bin_stops(self, plan, bins):
        for seq, (cp, bin_obj) in enumerate(bins, start=1):
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

    def _sync_household_stop(self, plan):
        # Area-scoped household stop (customer_id=None) — the assignment signal
        # fans it out to every active customer in the plan's panchayat.
        TripPlanCollectionPoint.objects.update_or_create(
            trip_plan_id=plan,
            collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
            customer_id=None,
            defaults={
                "sequence": 1,
                "is_active": True,
                "is_deleted": False,
            },
        )

    def _generate_assignment(self, plan, trip_date):
        assignment, _ = DailyTripAssignment.objects.get_or_create(
            trip_plan_id=plan,
            trip_date=trip_date,
            is_deleted=False,
            defaults={
                "staff_template_id": plan.staff_template_id,
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
                "scheduled_time": plan.scheduled_time,
                "status": DailyTripAssignment.STATUS_SCHEDULED,
                "approval_status": DailyTripAssignment.APPROVAL_APPROVED,
            },
        )
        return assignment

    def _reset_bin_assignment(self, assignment):
        """Return the bin trip to a fresh, collectable demo state (idempotent)."""
        BinCollectionEvent.objects.filter(trip_assignment_id=assignment).delete()
        DailyTripLog.objects.filter(trip_assignment_id=assignment).delete()
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment
        ).update(
            status=DailyTripCollectionPoint.STATUS_PENDING,
            is_collected=False,
            collected_at=None,
            collected_weight_kg=None,
        )
        assignment.status = DailyTripAssignment.STATUS_SCHEDULED
        assignment.approval_status = DailyTripAssignment.APPROVAL_APPROVED
        assignment.actual_start_time = None
        assignment.actual_end_time = None
        assignment.save(update_fields=[
            "status", "approval_status", "actual_start_time",
            "actual_end_time", "updated_at",
        ])

    def _reset_household_assignment(self, assignment):
        DailyTripLog.objects.filter(trip_assignment_id=assignment).delete()
        DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=assignment
        ).update(
            status=DailyTripHouseholdCollection.STATUS_PENDING,
            is_collected=False,
            collected_at=None,
            collected_weight_kg=None,
            waste_collection_id=None,
        )
        assignment.status = DailyTripAssignment.STATUS_SCHEDULED
        assignment.approval_status = DailyTripAssignment.APPROVAL_APPROVED
        assignment.actual_start_time = None
        assignment.actual_end_time = None
        assignment.save(update_fields=[
            "status", "approval_status", "actual_start_time",
            "actual_end_time", "updated_at",
        ])
