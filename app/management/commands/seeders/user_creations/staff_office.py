from django.utils import timezone

from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.password_encryption import encrypt_password


DEFAULT_STAFF_PASSWORD = "Staff123"


def _get_dept(company, project, code):
    return Department.objects.filter(
        company_id=company, project_id=project,
        department_code=code, is_deleted=False,
    ).first()


def _get_desg(company, project, name, department):
    return Designation.objects.filter(
        company_id=company, project_id=project,
        designation_name=name, department_id=department,
        is_deleted=False,
    ).first()


class StaffOfficeSeeder:
    group = "user-creation"

    def run(self):
        company = Company.objects.filter(is_deleted=False).first()
        if not company:
            company, _ = Company.objects.get_or_create(
                name="IWMS",
                defaults={
                    "description": "Integrated Waste Management System",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        project = Project.objects.filter(company_id=company, is_deleted=False).first()
        if not project:
            project_name = f"{company.name} Main Project"
            project, _ = Project.objects.get_or_create(
                name=project_name,
                company_id=company,
                defaults={
                    "description": f"Default project for {company.name}",
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        district = District.objects.filter(is_deleted=False).first()
        city = City.objects.filter(is_deleted=False).first()
        zone = Zone.objects.filter(is_deleted=False).first()
        ward = Ward.objects.filter(is_deleted=False).first()

        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            print("UserType 'staff' missing. Skipping Staffcreation seeding.")
            return

        role_admin = StaffUserType.objects.filter(name__iexact="Admin", usertype_id=staff_type).first()
        role_driver = StaffUserType.objects.filter(name__iexact="Company Driver", usertype_id=staff_type).first()
        role_operator = StaffUserType.objects.filter(name__iexact="Company Operator", usertype_id=staff_type).first()
        role_supervisor = StaffUserType.objects.filter(name__iexact="Company Supervisor", usertype_id=staff_type).first()

        if not all([role_admin, role_driver, role_operator, role_supervisor]):
            print("Required staff roles missing. Run StaffUserTypeSeeder first.")
            return

        # Department & Designation lookups
        dept_it    = _get_dept(company, project, "IT")
        dept_ops   = _get_dept(company, project, "OPS")
        dept_trans = _get_dept(company, project, "TRANS")
        dept_field = _get_dept(company, project, "FIELD")

        desg_sys_admin   = _get_desg(company, project, "System Administrator", dept_it)
        desg_driver      = _get_desg(company, project, "Driver", dept_trans)
        desg_operator    = _get_desg(company, project, "Operator", dept_ops)
        desg_supervisor  = _get_desg(company, project, "Operations Supervisor", dept_ops)

        # Passwords: min 6 chars, at least 1 uppercase + 1 lowercase + 1 digit
        staff_passwords = {
            "Sathya":   "Sathya1",
            "Gokul":    "Gokul12",
            "Arjun":    "Arjun12",
            "Vikram":   "Vikram1",
            "Karan":    "Karan12",
            "Suresh":   "Suresh1",
            "Mani":     "Mani123",
            "Rahul":    "Rahul12",
            "Prakash":  "Prakash1",
            "Deepak":   "Deepak1",
            "Naveen":   "Naveen1",
            "Santhosh": "Santhosh1",
            "Ajay":     "Ajay123",
            "Anita":    "Anita12",
            "Kumar":    "Kumar12",
            "Priya":    "Priya12",
        }

        def make_entry(name, dept_obj, desg_obj, dept_name_txt, desg_name_txt, role, grade, site, salary="Monthly"):
            return {
                "employee_name": name,
                "department": dept_name_txt,
                "designation": desg_name_txt,
                "department_id": dept_obj,
                "designation_id": desg_obj,
                "grade": grade,
                "site_name": site,
                "salary_type": salary,
                "active_status": True,
                "company_id": company,
                "project_id": project,
                "district_id": district,
                "city_id": city,
                "zone_id": zone,
                "ward_id": ward,
                "user_type_id": staff_type,
                "staffusertype_id": role,
                "approval_status": Staffcreation.APPROVAL_APPROVED,
                "login_enabled": True,
                "password": staff_passwords.get(name, DEFAULT_STAFF_PASSWORD),
            }

        staff_list = [
            make_entry("Sathya", dept_it,    desg_sys_admin,  "Information Technology", "System Administrator", role_admin,      "A", "HQ"),
            make_entry("Gokul",  dept_trans, desg_driver,     "Transport",              "Driver",               role_driver,     "B", "Depot-1"),
            make_entry("Arjun",  dept_trans, desg_driver,     "Transport",              "Driver",               role_driver,     "B", "Depot-2"),
            make_entry("Vikram", dept_trans, desg_driver,     "Transport",              "Driver",               role_driver,     "B", "Depot-3"),
            make_entry("Karan",  dept_trans, desg_driver,     "Transport",              "Driver",               role_driver,     "B", "Depot-1"),
            make_entry("Suresh", dept_trans, desg_driver,     "Transport",              "Driver",               role_driver,     "B", "Depot-2"),
            make_entry("Mani",   dept_trans, desg_driver,     "Transport",              "Driver",               role_driver,     "B", "Depot-3"),
            make_entry("Rahul",  dept_ops,   desg_operator,   "Operations",             "Operator",             role_operator,   "B", "Depot-1"),
            make_entry("Prakash",dept_ops,   desg_operator,   "Operations",             "Operator",             role_operator,   "B", "Depot-2"),
            make_entry("Deepak", dept_ops,   desg_operator,   "Operations",             "Operator",             role_operator,   "B", "Depot-3"),
            make_entry("Naveen", dept_ops,   desg_operator,   "Operations",             "Operator",             role_operator,   "B", "Depot-1"),
            make_entry("Santhosh",dept_ops,  desg_operator,   "Operations",             "Operator",             role_operator,   "B", "Depot-2"),
            make_entry("Ajay",   dept_ops,   desg_operator,   "Operations",             "Operator",             role_operator,   "B", "Depot-3"),
            make_entry("Anita",  dept_ops,   desg_supervisor, "Operations",             "Operations Supervisor",role_supervisor, "A", "Depot-1"),
            make_entry("Kumar",  dept_ops,   desg_supervisor, "Operations",             "Operations Supervisor",role_supervisor, "A", "Depot-2"),
            make_entry("Priya",  dept_field, desg_supervisor, "Field Operations",       "Operations Supervisor",role_supervisor, "A", "Depot-3"),
        ]

        now = timezone.now()
        for staff_data in staff_list:
            raw_password = staff_data.pop("password", None) or DEFAULT_STAFF_PASSWORD
            encrypted_password = encrypt_password(raw_password)

            staff = Staffcreation.objects.filter(employee_name=staff_data["employee_name"]).first()

            if staff:
                for key, value in staff_data.items():
                    setattr(staff, key, value)
                staff.save()
                created = False
            else:
                staff = Staffcreation(**staff_data)
                staff.password = encrypted_password
                staff.password_crt_date = now
                staff.save()
                created = True

            if not staff.password or created:
                staff.password = encrypted_password
                staff.password_crt_date = now
                staff.save(update_fields=["password", "password_crt_date"])

            action = "Created" if created else "Updated"
            print(f"  Staff '{staff.employee_name}' ({action})")

        print("---Staffcreation seeded---")
