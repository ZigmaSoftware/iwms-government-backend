from app.management.commands.seeders.base import BaseSeeder
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType


class StaffUserTypeSeeder(BaseSeeder):
    name = "staff_user_type"

    # Must use the stored choice values (snake_case) from StaffUserType.STAFF_ROLE_CHOICES
    STAFF_ROLES = [
        "company_admin",
        "company_driver",
        "company_operator",
        "company_supervisor",
        "company_user",
    ]

    def run(self):
        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            self.log_error("UserType 'staff' not found. Run UserTypeSeeder first.")
            return

        for role_name in self.STAFF_ROLES:
            StaffUserType.objects.get_or_create(
                usertype_id=staff_type,
                name=role_name,
                defaults={"is_active": True, "is_deleted": False},
            )

        self.log(f"---Staff user types seeded ({len(self.STAFF_ROLES)} records)---")
