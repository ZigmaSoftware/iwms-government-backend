from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class AlternativeStaffTemplateSeeder(BaseSeeder):
    name = "alternative_staff_template"

    def run(self):
        staff_templates = list(
            StaffTemplate.objects.filter(is_deleted=False, status="ACTIVE").order_by("created_at")[:15]
        )
        if not staff_templates:
            self.log("No StaffTemplate found. Seeder aborted.")
            return

        all_staff = list(
            Staffcreation.objects.filter(is_active=True, is_deleted=False).order_by("staff_unique_id")
        )
        if len(all_staff) < 3:
            self.log("Insufficient staff found (need at least 3). Seeder aborted.")
            return

        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={"description": "Integrated Waste Management System", "is_active": True, "is_deleted": False},
        )
        project, _ = Project.objects.get_or_create(
            name=f"{company.name} Main Project",
            company_id=company,
            defaults={"description": f"Default project for {company.name}", "is_active": True, "is_deleted": False},
        )

        approver = all_staff[2]
        created_count = 0

        for idx, staff_template in enumerate(staff_templates):
            driver_idx = (idx + 1) % len(all_staff)
            operator_idx = (idx + 2) % len(all_staff)
            extra_idx = (idx + 3) % len(all_staff)

            alt_driver = all_staff[driver_idx]
            alt_operator = all_staff[operator_idx]
            alt_extra = all_staff[extra_idx]

            comp = getattr(staff_template, "company_id", None) or company
            proj = getattr(staff_template, "project_id", None) or project

            _, created = AlternativeStaffTemplate.objects.get_or_create(
                staff_template=staff_template,
                company_id=comp,
                project_id=proj,
                driver_id=alt_driver,
                operator_id=alt_operator,
                defaults={
                    "extra_operator_id": [str(alt_extra.staff_unique_id)],
                    "change_reason": f"Temporary substitution #{idx + 1}",
                    "change_remarks": f"Seeder-generated alternative for template {staff_template.pk}",
                    "approved_by": approver,
                    "approval_status": "APPROVED",
                },
            )
            if created:
                created_count += 1

        self.log(f"---Alternative staff templates seeded | created={created_count} | total={len(staff_templates)}---")
