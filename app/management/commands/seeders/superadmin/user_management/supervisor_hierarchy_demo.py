from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.masters.transport_masters.fuel import Fuel
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.superadmin.role_management.governmentStaffUserType import (
    GovernmentStaffUserType,
)
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.user_management.staffcreation import Staffcreation


class SupervisorHierarchyDemoSeeder(BaseSeeder):
    """Extra staff + staff templates + one alternative staff template, all
    under `supervisor_user`'s own geo hierarchy (same panchayat as
    driver_user's trip), so the supervisor app's "Substitute staff" flow has
    real hierarchy-scoped data to pick from — a dropdown of staff templates
    and alternative staff templates that `supervisor_user` is actually
    responsible for, distinct from driver_user/operator_user's own template.

    Must run AFTER SupervisorUserSeeder (needs supervisor_user's geo fields +
    StaffDataScope already set by that seeder).
    """

    name = "SupervisorHierarchyDemoSeeder"

    DRIVER_ROLE = "govt_panchayat_driver"
    OPERATOR_ROLE = "govt_panchayat_operator"

    EXTRA_DRIVERS = [
        ("driver2_user", "Driver Two", "Driver2@123"),
        ("driver3_user", "Driver Three", "Driver3@123"),
    ]
    EXTRA_OPERATORS = [
        ("operator2_user", "Operator Two", "Operator2@123"),
        ("operator3_user", "Operator Three", "Operator3@123"),
    ]

    # (vehicle_no, vehicle_type, fuel_type, capacity_kg) — spare vehicles under
    # the supervisor's own hierarchy, for the "vehicle breakdown" replacement
    # flow's "available vehicles" dropdown.
    EXTRA_VEHICLES = [
        ("TN33ZZ9001", "Mini Truck", "Petrol", 1500),
        ("TN33ZZ9002", "Tipper Truck", "Diesel", 4000),
    ]

    def run(self):
        supervisor = Staffcreation.objects.filter(
            username="supervisor_user", is_deleted=False
        ).first()
        if not supervisor or not supervisor.panchayat_id:
            self.log(
                "supervisor_user missing or has no geo scope yet — run "
                "SupervisorUserSeeder first. Skipping."
            )
            return

        user_type = UserType.objects.filter(name__iexact="government").first()
        if not user_type:
            self.log("Government UserType missing — skipping.")
            return

        driver_role, _ = GovernmentStaffUserType.objects.get_or_create(
            name=self.DRIVER_ROLE,
            usertype_id=user_type,
            defaults={"level": "panchayat", "is_active": True, "is_deleted": False},
        )
        operator_role, _ = GovernmentStaffUserType.objects.get_or_create(
            name=self.OPERATOR_ROLE,
            usertype_id=user_type,
            defaults={"level": "panchayat", "is_active": True, "is_deleted": False},
        )

        geo = {
            "state": supervisor.state,
            "district": supervisor.district,
            "area_type": supervisor.area_type,
            "corporation": supervisor.corporation,
            "municipality": supervisor.municipality,
            "town_panchayat": supervisor.town_panchayat,
            "panchayat_union": supervisor.panchayat_union,
            "panchayat": supervisor.panchayat,
        }

        drivers = [
            self._upsert_staff(username, name, password, user_type, driver_role, geo)
            for username, name, password in self.EXTRA_DRIVERS
        ]
        operators = [
            self._upsert_staff(username, name, password, user_type, operator_role, geo)
            for username, name, password in self.EXTRA_OPERATORS
        ]

        templates = [
            self._get_or_create_template(drivers[i], operators[i], geo)
            for i in range(len(drivers))
        ]

        vehicles_created = self._seed_vehicles(geo)

        today = timezone.localdate()
        alt, created = AlternativeStaffTemplate.objects.get_or_create(
            staff_template=templates[0],
            defaults={
                "driver_id": drivers[1],
                "operator_id": operators[1],
                "from_date": today,
                "to_date": today + timedelta(days=30),
                "change_reason": "Demo substitution",
                "change_remarks": "Seeded for supervisor app testing.",
                "approval_status": AlternativeStaffTemplate.APPROVAL_STATUS_CHOICES[1][0],
                **geo,
            },
        )

        self.log(
            f"Seeded {len(drivers)} extra driver(s), {len(operators)} extra "
            f"operator(s), {len(templates)} staff template(s), "
            f"{vehicles_created} spare vehicle(s) under "
            f"{supervisor.panchayat.panchayat_name}; "
            f"{'created' if created else 'reused'} alternative staff template "
            f"{alt.display_code} substituting onto {templates[0].display_code}."
        )

    def _upsert_staff(self, username, name, password, user_type, role, geo):
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
                **geo,
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
            for field, value in geo.items():
                setattr(staff, field, value)
            staff.save()
        return staff

    def _seed_vehicles(self, geo):
        created = 0
        for vehicle_no, vtype_name, fuel_name, capacity in self.EXTRA_VEHICLES:
            vehicle_type = VehicleTypeCreation.objects.filter(
                vehicleType=vtype_name
            ).first()
            fuel_type = Fuel.objects.filter(fuel_type=fuel_name).first()
            if not vehicle_type or not fuel_type:
                self.log(
                    f"VehicleType '{vtype_name}' or Fuel '{fuel_name}' not "
                    f"found — skipping {vehicle_no}."
                )
                continue

            _, was_created = VehicleCreation.objects.get_or_create(
                vehicle_no=vehicle_no,
                defaults={
                    "vehicle_type": vehicle_type,
                    "fuel_type": fuel_type,
                    "capacity": capacity,
                    "vehicle_condition": "NEW",
                    "is_active": True,
                    "is_deleted": False,
                    **geo,
                },
            )
            if was_created:
                created += 1
        return created

    def _get_or_create_template(self, driver, operator, geo):
        template = StaffTemplate.objects.filter(
            driver_id=driver, operator_id=operator, is_deleted=False
        ).first()
        if template is None:
            template = StaffTemplate.objects.create(
                driver_id=driver,
                operator_id=operator,
                approval_status=StaffTemplate.ApprovalStatus.APPROVED,
                status=StaffTemplate.Status.ACTIVE,
                is_active=True,
                is_deleted=False,
                **geo,
            )
        else:
            for field, value in geo.items():
                setattr(template, field, value)
            template.approval_status = StaffTemplate.ApprovalStatus.APPROVED
            template.status = StaffTemplate.Status.ACTIVE
            template.is_active = True
            template.is_deleted = False
            template.save()
        return template
