from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.base_models import Account


class StaffTemplateSeeder(BaseSeeder):
    name = "staff_template"

    # 7 auth-user username pairs (from auth_user_seeder)
    USERNAME_PAIRS = [
        ("driver_user",  "operator_user"),
        ("driver2_user", "operator2_user"),
        ("driver3_user", "operator3_user"),
        ("driver4_user", "operator4_user"),
        ("driver5_user", "operator5_user"),
        ("driver6_user", "operator6_user"),
        ("driver7_user", "operator7_user"),
    ]

    # 6 named employee pairs (from staff_office seeder)
    NAMED_PAIRS = [
        ("Gokul",  "Rahul"),
        ("Arjun",  "Prakash"),
        ("Vikram", "Deepak"),
        ("Karan",  "Naveen"),
        ("Suresh", "Santhosh"),
        ("Mani",   "Ajay"),
    ]

    # 2 cross-pairs to reach 15 total
    CROSS_PAIRS = [
        ("driver_user",  "operator2_user"),
        ("driver2_user", "operator3_user"),
    ]

    def _get_account(self, staff):
        if not staff:
            return None
        account, _ = Account.objects.get_or_create(staff=staff)
        return account

    def _resolve_by_username(self, username):
        return (
            Staffcreation.objects
            .filter(username__iexact=username, is_active=True, is_deleted=False)
            .order_by("staff_unique_id")
            .first()
        )

    def _resolve_by_name(self, employee_name):
        return (
            Staffcreation.objects
            .filter(employee_name__iexact=employee_name, is_active=True, is_deleted=False)
            .order_by("staff_unique_id")
            .first()
        )

    def _ensure_company_project(self, *staff_members):
        for staff in staff_members:
            if staff:
                company = getattr(staff, "company_id", None)
                project = getattr(staff, "project_id", None)
                if company and project:
                    return company, project

        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={"description": "Integrated Waste Management System", "is_active": True, "is_deleted": False},
        )
        project, _ = Project.objects.get_or_create(
            name=f"{company.name} Main Project",
            company_id=company,
            defaults={"description": f"Default project for {company.name}", "is_active": True, "is_deleted": False},
        )
        return company, project

    def _create_template(self, driver, operator):
        if not driver or not operator:
            return False
        company, project = self._ensure_company_project(driver, operator)
        account = self._get_account(driver)
        _, created = StaffTemplate.objects.get_or_create(
            driver_id=driver,
            operator_id=operator,
            defaults={
                "company_id": company,
                "project_id": project,
                "extra_operator_id": [],
                "created_by": account,
                "updated_by": account,
                "approved_by": driver,
                "status": "ACTIVE",
                "approval_status": "APPROVED",
            },
        )
        return created

    def run(self):
        created_count = 0
        skipped = 0

        for driver_username, operator_username in self.USERNAME_PAIRS:
            driver = self._resolve_by_username(driver_username)
            operator = self._resolve_by_username(operator_username)
            if self._create_template(driver, operator):
                created_count += 1
            else:
                skipped += 1

        for driver_name, operator_name in self.NAMED_PAIRS:
            driver = self._resolve_by_name(driver_name)
            operator = self._resolve_by_name(operator_name)
            if self._create_template(driver, operator):
                created_count += 1
            else:
                skipped += 1

        for driver_username, operator_username in self.CROSS_PAIRS:
            driver = self._resolve_by_username(driver_username)
            operator = self._resolve_by_username(operator_username)
            if self._create_template(driver, operator):
                created_count += 1
            else:
                skipped += 1

        self.log(f"---StaffTemplate seeded | created={created_count} | skipped={skipped}---")
