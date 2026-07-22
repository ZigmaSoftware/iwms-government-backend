# seeders/role_assign/usertype.py

from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.role_management.userType import UserType


class UserTypeSeeder(BaseSeeder):
    name = "user_type"

    def run(self):
        allowed_types = ["Government"]

        # -------------------------------------------------
        # Create / ensure only required user types exist
        # -------------------------------------------------
        for name in allowed_types:
            UserType.objects.get_or_create(
                name=name,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        self.log("---User types seeded (Government)---")
