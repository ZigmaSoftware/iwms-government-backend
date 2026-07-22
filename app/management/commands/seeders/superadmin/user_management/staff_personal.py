from app.models.superadmin.user_management.staffcreation import Staffcreation, StaffPersonalDetails


class StaffPersonalSeeder:
    group = "user-creation"

    def run(self):
        for staff in Staffcreation.objects.all():
            emp_id = staff.emp_id or Staffcreation._derive_emp_id(staff.staff_unique_id)
            contact_mobile = f"900{emp_id[-7:]}"
            contact_email = f"{staff.employee_name.replace(' ', '').lower()}@example.com"

            staff_personal, created = StaffPersonalDetails.objects.get_or_create(
                staff=staff,
                defaults={
                    "staff_unique_id": staff.staff_unique_id,
                    "gender": "Male",
                    "blood_group": "O+",
                    "contact_mobile": contact_mobile,
                    "contact_email": contact_email,
                }
            )

        print("---StaffPersonalDetails seeded---")
