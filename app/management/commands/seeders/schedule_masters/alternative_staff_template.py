from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


class AlternativeStaffTemplateSeeder(BaseSeeder):
    name = "AlternativeStaffTemplateSeeder"

    # (alt_driver_username, alt_operator_username, change_reason)
    ALT_ASSIGNMENTS = [
        ("geetha.lakshmi", "priya.devi",   "Sick leave"),
        ("priya.devi",     "geetha.lakshmi","Annual leave"),
        ("muthu.samy",     "anbu.arasan",  "Emergency replacement"),
        ("anbu.arasan",    "ravi.kumar",   "Training duty"),
        ("ravi.kumar",     "geetha.lakshmi","Vehicle change"),
    ]

    def run(self):
        templates = StaffTemplate.objects.filter(
            is_deleted=False, status=StaffTemplate.Status.ACTIVE
        ).order_by("created_at")

        if not templates.exists():
            self.log("No StaffTemplates found — run StaffTemplateSeeder first.")
            return

        count = 0
        for idx, (driver_username, operator_username, change_reason) in enumerate(
            self.ALT_ASSIGNMENTS
        ):
            template = templates[idx % templates.count()]

            driver = StaffcreationOfficeDetails.objects.filter(
                username=driver_username, is_deleted=False
            ).first()
            operator = StaffcreationOfficeDetails.objects.filter(
                username=operator_username, is_deleted=False
            ).first()

            if not driver or not operator:
                self.log(f"Staff not found for alt template {idx + 1} — skipping.")
                continue

            if AlternativeStaffTemplate.objects.filter(staff_template=template).exists():
                self.log(f"Alt template for '{template.display_code}' already exists — skipping.")
                continue

            AlternativeStaffTemplate.objects.create(
                staff_template=template,
                driver_id=driver,
                operator_id=operator,
                change_reason=change_reason,
                approval_status="APPROVED",
            )
            count += 1

        self.log(f"---Alternative staff templates seeded ({count} created)---")
