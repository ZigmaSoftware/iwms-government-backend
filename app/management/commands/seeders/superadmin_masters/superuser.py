from django.contrib.auth import get_user_model
from django.db import transaction

from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.role_management.staffUserType import StaffUserType


class PlatformSuperUserSeeder(BaseSeeder):
    name = "platform_superuser"

    @transaction.atomic
    def run(self):
        UserModel = get_user_model()
        username = "super_admin"
        password = "admin@123"

        platform_type = (
            UserType.objects.filter(name__iexact="platform").first()
        )
        if not platform_type:
            platform_type = UserType.objects.create(name="Platform")

        superadmin_role = (
            StaffUserType.objects.filter(
                usertype_id=platform_type,
                name__iexact="superadmin",
            ).first()
        )
        if not superadmin_role:
            superadmin_role = StaffUserType.objects.create(
                usertype_id=platform_type,
                name="superadmin",
                is_active=True,
                is_deleted=False,
            )

        user = UserModel.objects.filter(username=username).first()
        if user:
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.is_deleted = False
            user.user_type_id = None
            user.staffusertype_id = None
            user.staff_id = None
            user.customer_id = None
            user.set_password(password)
            user.save()
            self.log(f"Updated platform superuser: {username}")
            return

        user = UserModel.objects.create_superuser(
            username=username,
            password=password,
        )
        user.save()
        self.log(f"---Created platform superuser: {username}---")
