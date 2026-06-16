from app.management.commands.seeders.base import BaseSeeder
from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.userType import UserType


class ContractorUserTypeSeeder(BaseSeeder):
    name = "contractor_user_type"

    def run(self):
        contractor_type = UserType.objects.filter(name__iexact="contractor").first()
        if not contractor_type:
            self.log_error("UserType 'contractor' not found. Run UserTypeSeeder first.")
            return

        for role_name, _ in ContractorUserType.CONTRACTOR_ROLE_CHOICES:
            role, created = ContractorUserType.objects.get_or_create(
                usertype_id=contractor_type,
                name=role_name,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created and (role.is_deleted or not role.is_active):
                role.is_deleted = False
                role.is_active = True
                role.save(update_fields=["is_deleted", "is_active"])

        self.log("---Contractor user types seeded---")
