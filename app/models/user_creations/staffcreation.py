import hashlib
from django.conf import settings
from django.db import models
from app.utils.base_models import Account, BaseMaster
from app.utils.comfun import generate_unique_id
from ..role_assigns.userType import UserType
from ..role_assigns.staffUserType import StaffUserType
from ..role_assigns.contractorUserType import ContractorUserType
from ..role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.utils.customer_qr import generate_customer_qr_content


def generate_staff_unique_id():
    """Generate readable prefixed ID, e.g., ST-20251028001"""
    return f"STC-{generate_unique_id()}"


class StaffcreationOfficeDetails(BaseMaster):
    APPROVAL_PENDING = "PENDING"
    APPROVAL_APPROVED = "APPROVED"
    APPROVAL_REJECTED = "REJECTED"
    APPROVAL_SUSPENDED = "SUSPENDED"

    APPROVAL_STATUS_CHOICES = [
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
        (APPROVAL_SUSPENDED, "Suspended"),
    ]

    staff_unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        editable=False,
        default=generate_staff_unique_id,
    )
    emp_id = models.CharField(
        max_length=8,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    employee_name = models.CharField(max_length=200)
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

    grade = models.CharField(max_length=50, blank=True, null=True)
    site_name = models.CharField(max_length=200, blank=True, null=True)
    staff_head = models.CharField(max_length=200, blank=True, null=True)
    staff_head_id = models.CharField(max_length=30, blank=True, null=True)
    employee_known = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(upload_to="staff_photos/", blank=True, null=True)
    qr_code = models.ImageField(upload_to="staff_qr/", blank=True, null=True)
    active_status = models.BooleanField(default=True)
    salary_type = models.CharField(max_length=50, blank=True, null=True)

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
        null=True
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

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_PENDING,
        db_index=True,
    )
    login_enabled = models.BooleanField(default=False, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_staff_users",
        db_column="approved_by",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(null=True, blank=True)
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

    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.SET_NULL,
        related_name="staff_location",
        to_field="unique_id",
        db_column="location_node_id",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee_name} ({self.staff_unique_id})"

    @staticmethod
    def _derive_emp_id(staff_unique_id, salt=0):
        digest = hashlib.sha1(f"{staff_unique_id}:{salt}".encode("utf-8")).hexdigest()
        numeric = int(digest[:12], 16) % 10**8
        return f"{numeric:08d}"

    def _ensure_emp_id(self):
        if self.emp_id or not self.staff_unique_id:
            return

        for salt in range(100):
            candidate = self._derive_emp_id(self.staff_unique_id, salt)
            exists = (
                StaffcreationOfficeDetails.objects.filter(emp_id=candidate)
                .exclude(pk=self.pk)
                .exists()
            )
            if not exists:
                self.emp_id = candidate
                return

        self.emp_id = self._derive_emp_id(self.staff_unique_id, 999999)

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
