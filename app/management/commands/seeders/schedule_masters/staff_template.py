from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


class StaffTemplateSeeder(BaseSeeder):
    name = "StaffTemplateSeeder"

    # (driver_username, operator_username)
    TEMPLATES = [
        ("ravi.kumar",     "priya.devi"),
        ("anbu.arasan",    "muthu.samy"),
        ("ravi.kumar",     "muthu.samy"),
        ("anbu.arasan",    "priya.devi"),
        ("muthu.samy",     "ravi.kumar"),
    ]

    def run(self):
        count = 0
        for driver_username, operator_username in self.TEMPLATES:
            driver = StaffcreationOfficeDetails.objects.filter(
                username=driver_username, is_deleted=False
            ).first()
            operator = StaffcreationOfficeDetails.objects.filter(
                username=operator_username, is_deleted=False
            ).first()

            if not driver:
                self.log(f"Driver '{driver_username}' not found — skipping.")
                continue
            if not operator:
                self.log(f"Operator '{operator_username}' not found — skipping.")
                continue

            exists = StaffTemplate.objects.filter(
                driver_id=driver, operator_id=operator, is_deleted=False
            ).exists()
            if not exists:
                StaffTemplate.objects.create(
                    driver_id=driver,
                    operator_id=operator,
                    approval_status=StaffTemplate.ApprovalStatus.APPROVED,
                    status=StaffTemplate.Status.ACTIVE,
                    is_active=True,
                    is_deleted=False,
                )
                count += 1

        self.log(f"---Staff templates seeded ({count} created)---")
