from django.db import models
from app.utils.base_models import Account, BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.customer_qr import generate_customer_qr_content
from app.utils.file_validators import validate_pdf_upload


def generate_staff_unique_id():
    """Generate readable prefixed ID, e.g., ST-20251028001"""
    return f"STC-{generate_unique_id()}"


class StaffcreationOfficeDetails(BaseMaster):
    staff_unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        editable=False,
        default=generate_staff_unique_id,
    )
    emp_id = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    employee_name = models.CharField(max_length=200)
    staff_config_name = models.CharField(max_length=150, blank=True, null=True)
    doj = models.DateField(blank=True, null=True)
    department = models.CharField(max_length=200, blank=True, null=True)
    designation = models.CharField(max_length=200, blank=True, null=True)
    department_id = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="department_id",
        related_name="staff_members",
    )
    designation_id = models.ForeignKey(
        Designation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="designation_id",
        related_name="staff_members",
    )

    staff_head = models.CharField(max_length=200, blank=True, null=True)
    staff_head_id = models.CharField(max_length=30, blank=True, null=True)
    photo = models.ImageField(upload_to="staff_photos/", blank=True, null=True)
    attendance_reg_image = models.ImageField(
        upload_to="attendance/registration/",
        blank=True,
        null=True,
        help_text="Reference face image used for attendance recognition.",
    )
    qr_code = models.ImageField(upload_to="staff_qr/", blank=True, null=True)
    active_status = models.BooleanField(default=True)

    # Driving Licence Fields
    driving_licence_no = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    driving_licence_expiry_date = models.DateField(
        blank=True,
        null=True,
    )
    driving_licence_file = models.FileField(
        upload_to="staff_licences/",
        blank=True,
        null=True,
        validators=[validate_pdf_upload],
        help_text="Driving licence document (PDF, max 3 MB).",
    )
    driving_experience_years = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Driving experience in years.",
    )

    # =============================================
    # AUTHENTICATION FIELDS (from User model)
    # =============================================
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text="Required for platform super admins. Staff users may be created without it."
    )

    office_email = models.EmailField(
        null=True,
        blank=True,
    )

    password = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Django auth password field"
    )

    password_crt_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last password change"
    )

    previous_password = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Previous encrypted password for reuse prevention"
    )

    is_staff = models.BooleanField(
        default=False,
        help_text="Django admin-site access flag (not a business role).",
    )

    is_superuser = models.BooleanField(default=False)

    login_enabled = models.BooleanField(default=False, db_index=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Type Links
    user_type_id = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="user_type_id",
        related_name="staff_users"
    )

    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="staffusertype_id",
        related_name="staff_users"
    )

    contractorusertype_id = models.ForeignKey(
        ContractorUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="contractorusertype_id",
        related_name="staff_users"
    )

    governmentusertype_id = models.ForeignKey(
        GovernmentStaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="governmentusertype_id",
        related_name="staff_users"
    )

    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee_name} ({self.staff_unique_id})"

    def _ensure_emp_id(self):
        if self.emp_id:
            return

        highest = 0
        existing_ids = StaffcreationOfficeDetails.objects.filter(
            emp_id__startswith="EMP-"
        ).values_list("emp_id", flat=True)
        for existing_id in existing_ids:
            suffix = str(existing_id).removeprefix("EMP-")
            if suffix.isdigit():
                highest = max(highest, int(suffix))

        self.emp_id = f"EMP-{highest + 1:06d}"

    def _regenerate_qr_code(self):
        file_content = generate_customer_qr_content({"id": self.staff_unique_id})
        file_name = f"{self.staff_unique_id}.png"
        if self.qr_code:
            self.qr_code.delete(save=False)
        self.qr_code.save(file_name, file_content, save=False)
        super().save(update_fields=["qr_code"])

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        if not self.emp_id:
            self._ensure_emp_id()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("emp_id")
                kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)

        if is_new:
            Account.objects.get_or_create(staff=self)

        if is_new or not self.qr_code:
            self._regenerate_qr_code()

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated users.
        Required by Django REST Framework's permission system.
        """
        return True


class StaffPersonalDetails(models.Model):
    staff = models.OneToOneField(
        StaffcreationOfficeDetails,
        on_delete=models.CASCADE,
        related_name="personal_details"
    )
    staff_unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        editable=False
    )
    marital_status = models.CharField(max_length=50, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    blood_group = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    physically_challenged = models.CharField(max_length=20, blank=True, null=True)
    present_address = models.JSONField(blank=True, null=True)
    permanent_address = models.JSONField(blank=True, null=True)
    contact_mobile = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(max_length=254, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Personal details for {self.staff.employee_name}"

    def save(self, *args, **kwargs):
        if self.staff and not self.staff_unique_id:
            self.staff_unique_id = self.staff.staff_unique_id
        super().save(*args, **kwargs)


# Backward compatibility alias
Staffcreation = StaffcreationOfficeDetails
