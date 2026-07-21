from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType


class GovernmentStaffUserTypeSeeder(BaseSeeder):
    name = "government_staff_user_type"

    def run(self):
        government_type = UserType.objects.filter(name__iexact="government").first()
        if not government_type:
            self.log_error("UserType 'government' not found. Run UserTypeSeeder first.")
            return

        count = 0
        for level_value, _ in GovernmentStaffUserType.GOVT_LEVEL_CHOICES:
            for role_name, _ in GovernmentStaffUserType.GOVT_ROLE_CHOICES:
                if not role_name.startswith(f"govt_{level_value}_"):
                    continue

                _, created = GovernmentStaffUserType.objects.get_or_create(
                    usertype_id=government_type,
                    name=role_name,
                    defaults={
                        "level": level_value,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    count += 1

        self.log(f"---Government staff user types seeded ({count} records)---")
