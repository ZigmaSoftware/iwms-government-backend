from django.contrib.auth.hashers import make_password
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.utils.hierarchy import copy_flat_geo, sync_staff_data_scope


class SupervisorUserSeeder(BaseSeeder):
    """Create a supervisor login (`supervisor_user` / `Supervisor123`) that is
    responsible for driver_user's trip, so it shows up in the supervisor app.

    The supervisor app lists `daily-trip-assignments/?mine=true`, which the
    backend scopes to trips whose TripPlan.supervisor_id == the requester. So we
    point the trip plan(s) behind driver_user's assignments at this supervisor.
    Must run AFTER DriverUserSeeder.
    """

    name = "SupervisorUserSeeder"

    USERNAME = "supervisor_user"
    PASSWORD = "Supervisor123"
    # Role name must contain "supervisor" so the mobile app routes to the
    # supervisor surface (UserModel.normalizeRole).
    ROLE_NAME = "govt_panchayat_supervisor"

    def run(self):
        user_type = UserType.objects.filter(name__iexact="government").first()
        if not user_type:
            self.log("Government UserType missing — skipping.")
            return

        role, _ = GovernmentStaffUserType.objects.get_or_create(
            name=self.ROLE_NAME,
            usertype_id=user_type,
            defaults={"level": "panchayat", "is_active": True, "is_deleted": False},
        )

        driver = Staffcreation.objects.filter(
            username="driver_user", is_deleted=False
        ).first()
        if not driver:
            self.log("driver_user not found — run DriverUserSeeder first. Skipping.")
            return

        today = timezone.localdate()
        assignments = list(
            DailyTripAssignment.objects.filter(
                trip_date=today,
                is_deleted=False,
                staff_template_id__driver_id=driver,
            )
        )
        if not assignments:
            self.log("driver_user has no trip today — run DriverUserSeeder. Skipping.")
            return

        # Create / update the supervisor login.
        supervisor, created = Staffcreation.objects.get_or_create(
            username=self.USERNAME,
            defaults={
                "employee_name": "Supervisor User",
                "password": make_password(self.PASSWORD),
                "user_type_id": user_type,
                "governmentusertype_id": role,
                "is_active": True,
                "is_deleted": False,
                "is_superuser": False,
                "login_enabled": True,
            },
        )
        if not created:
            supervisor.employee_name = "Supervisor User"
            supervisor.password = make_password(self.PASSWORD)
            supervisor.user_type_id = user_type
            supervisor.governmentusertype_id = role
            supervisor.staffusertype_id = None
            supervisor.is_active = True
            supervisor.is_deleted = False
            supervisor.is_superuser = False
            supervisor.login_enabled = True

        copy_flat_geo(supervisor, assignments[0])
        supervisor.save()

        # Data-scope the supervisor to the trip's geography. The scoped viewsets
        # (schedule-masters daily-trip-assignments / daily-trip-logs) deny any
        # non-super staff user with NO StaffDataScope row by default (empty
        # queryset), so without this the supervisor app's `mine=true` lists and
        # the home waste-graph come back EMPTY even though the trips exist.
        # Idempotent; scoped to the same flat geo the trip carries.
        sync_staff_data_scope(supervisor, assignments[0])

        # Make this supervisor responsible for the trip plan(s) behind
        # driver_user's assignments today.
        plan_ids = {a.trip_plan_id_id for a in assignments if a.trip_plan_id_id}
        updated = TripPlan.objects.filter(unique_id__in=plan_ids).update(
            supervisor_id=supervisor
        )

        # Make the supervisor lead every complaint team so complaints routed to
        # those teams surface in the supervisor grievance view (the ticket
        # queryset scopes to assigned_staff / team lead / department).
        teams = ComplaintTeam.objects.filter(is_deleted=False).update(
            lead_staff=supervisor
        )

        self.log(
            f"{'Created' if created else 'Updated'} supervisor login: "
            f"{self.USERNAME} / {self.PASSWORD} — owns {updated} trip plan(s) "
            f"covering {len(assignments)} of driver_user's trips today; "
            f"leads {teams} complaint team(s)."
        )
