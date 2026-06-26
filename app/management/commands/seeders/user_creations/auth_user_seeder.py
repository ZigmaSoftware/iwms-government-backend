from django.contrib.auth import get_user_model

from app.management.commands.seeders.base import BaseSeeder
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


class AuthUserSeeder(BaseSeeder):
    name = "AuthUserSeeder"

    def run(self):
        UserModel = get_user_model()

        staff_user_type = UserType.objects.filter(name__iexact="staff").first()
        driver_role = StaffUserType.objects.filter(name="company_driver").first()

        staff_members = StaffcreationOfficeDetails.objects.filter(
            is_deleted=False
        ).order_by("created_at")[:5]

        if not staff_members.exists():
            self.log("No staff found — run StaffOfficeSeeder first.")
            return

        count = 0
        for staff in staff_members:
            if not staff.username:
                continue
            if UserModel.objects.filter(username=staff.username).exists():
                self.log(f"User '{staff.username}' already exists — skipping.")
                continue

            user = UserModel(
                username=staff.username,
                user_type_id=staff_user_type,
                staffusertype_id=driver_role,
                staff_id=staff,
                is_active=True,
                is_deleted=False,
            )
            user.set_password("Staff@1234")
            user.save()
            count += 1
            self.log(f"Created auth user: {staff.username}")

        self.log(f"---Auth users seeded ({count} records)---")
