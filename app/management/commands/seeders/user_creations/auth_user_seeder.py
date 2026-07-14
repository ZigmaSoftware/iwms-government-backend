from django.contrib.auth import get_user_model

from app.management.commands.seeders.base import BaseSeeder
from app.models.role_assigns.userType import UserType
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


class AuthUserSeeder(BaseSeeder):
    name = "AuthUserSeeder"

    def run(self):
        UserModel = get_user_model()

        # Government-only project: seeded logins are government users. The
        # government role lives on the linked staff record
        # (staff.governmentusertype_id), so the auth user only needs the
        # "government" user type and its staff link.
        government_user_type = UserType.objects.filter(name__iexact="government").first()
        if not government_user_type:
            self.log("UserType 'government' not found — run UserTypeSeeder first. Skipping.")
            return

        staff_members = StaffcreationOfficeDetails.objects.filter(
            is_deleted=False,
            governmentusertype_id__isnull=False,
        ).order_by("created_at")[:5]

        if not staff_members.exists():
            self.log("No government staff found — run StaffOfficeSeeder first.")
            return

        count = 0
        normalized = 0
        for staff in staff_members:
            if not staff.username:
                continue

            existing = UserModel.objects.filter(username=staff.username).first()
            if existing:
                # Normalize legacy staff/contractor logins to government
                # (without touching the password) so re-seeding fixes old rows.
                changed = False
                if existing.user_type_id_id != government_user_type.pk:
                    existing.user_type_id = government_user_type
                    changed = True
                if existing.staffusertype_id_id is not None:
                    existing.staffusertype_id = None
                    changed = True
                if changed:
                    existing.save(update_fields=["user_type_id", "staffusertype_id", "updated_at"])
                    normalized += 1
                    self.log(f"Normalized auth user to government: {staff.username}")
                else:
                    self.log(f"User '{staff.username}' already government — skipping.")
                continue

            user = UserModel(
                username=staff.username,
                user_type_id=government_user_type,
                staffusertype_id=None,
                staff_id=staff,
                is_active=True,
                is_deleted=False,
            )
            user.set_password("Staff@1234")
            user.save()
            count += 1
            self.log(f"Created auth user: {staff.username}")

        self.log(f"---Auth users seeded ({count} created, {normalized} normalized)---")
