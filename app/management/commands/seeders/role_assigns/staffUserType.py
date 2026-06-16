# seeders/role_assign/staff_usertype.py

from app.management.commands.seeders.base import BaseSeeder
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType


class StaffUserTypeSeeder(BaseSeeder):
    name = "staff_user_type"

    def run(self):
        role_map = {
            "staff": ["Company Admin", "Company Driver", "Company Operator", "Company Supervisor", "Company User", "Company Project Admin"],
            "platform": ["SuperAdmin"],
        }

        for user_type_name, roles in role_map.items():
            user_type = UserType.objects.filter(name__iexact=user_type_name).first()
            if not user_type:
                self.log_error(
                    f"UserType '{user_type_name}' not found. Run UserTypeSeeder first."
                )
                continue

            for role_name in roles:
                StaffUserType.objects.get_or_create(
                    usertype_id=user_type,
                    name=role_name,
                    defaults={
                        "is_active": True,
                        "is_deleted": False,
                    }
                )

        self.log("---Staff user types seeded for staff and platform roles---")


