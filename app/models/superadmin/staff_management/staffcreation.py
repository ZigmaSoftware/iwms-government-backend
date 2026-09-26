from django.db import models
from app.utils.base_models import Account, BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.utils.customer_qr import generate_customer_qr_content
from app.utils.file_validators import validate_pdf_upload
from app.utils.app_feature_grants import APP_MODULE_CHOICES
from app.utils import ref_cache


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
    department_id = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_column="department_id",
        db_index=True,
    )
    designation_id = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_column="designation_id",
        db_index=True,
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
    # Face vector for the reference image above, written when attendance is
    # running on a provider that compares embeddings (InsightFace) so a punch
    # only has to process the incoming selfie instead of both images.
    # Stays null under CompreFace, which compares the two image files on its
    # own server and has nothing to cache here. Because it is only a cache of
    # `attendance_reg_image`, it is cleared whenever that image is replaced
    # and can always be rebuilt from it.
    face_embedding = models.JSONField(
        blank=True,
        null=True,
        editable=False,
        help_text=(
            "Cached face vector derived from attendance_reg_image. Provider-"
            "specific; cleared and recomputed when the reference image changes."
        ),
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

    # Mobile push notifications (driver/operator/supervisor apps) — the
    # device's current FCM registration token, refreshed on each login/token
    # rotation. Mirrors `CustomerCreation.fcm_token` for the citizen app.
    fcm_token = models.CharField(max_length=255, null=True, blank=True)

    # Type Links
    # Which mobile app this staff member lands in. Set explicitly rather than
    # guessed from the role name, so an unrelated web permission can never add
    # a surface the person has no screens for. Which apps they may actually
    # sign into is ticked on their StaffAccessConfiguration.
    app_module = models.CharField(
        max_length=20,
        choices=APP_MODULE_CHOICES,
        null=True,
        blank=True,
        db_column="app_module",
        help_text="Mobile app this user lands in. Leave blank for web-only staff.",
    )

    user_type_id = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_column="user_type_id",
        db_index=True,
    )

    staffusertype_id = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_column="staffusertype_id",
        db_index=True,
    )

    contractorusertype_id = models.CharField(
        max_length=35,
        null=True,
        blank=True,
        db_column="contractorusertype_id",
        db_index=True,
    )

    governmentusertype_id = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_column="governmentusertype_id",
        db_index=True,
    )

    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

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
    def data_scopes(self):
        """StaffDataScope rows for this staff (plain staff_id); replaces the
        reverse FK accessor."""
        from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope

        return StaffDataScope.objects.filter(staff_id=self.staff_unique_id)

    @property
    def personal_details(self):
        """This staff's StaffPersonalDetails row (keyed by the same
        staff_unique_id), or None; replaces the reverse one-to-one accessor."""
        return ref_cache.get(StaffPersonalDetails, self.staff_unique_id)

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated users.
        Required by Django REST Framework's permission system.
        """
        return True

    # =============================
    # PLAIN-STRING RELATION LOOKUPS
    # =============================
    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def department_ref(self):
        return self._lookup("app.models.masters.department.Department", self.department_id)

    @property
    def designation_ref(self):
        return self._lookup("app.models.masters.designation.Designation", self.designation_id)

    @property
    def user_type(self):
        return self._lookup("app.models.superadmin.role_management.userType.UserType", self.user_type_id)

    @property
    def staffusertype(self):
        return self._lookup("app.models.superadmin.role_management.staffUserType.StaffUserType", self.staffusertype_id)

    @property
    def contractorusertype(self):
        return self._lookup("app.models.superadmin.role_management.contractorUserType.ContractorUserType", self.contractorusertype_id)

    @property
    def governmentusertype(self):
        return self._lookup("app.models.superadmin.role_management.governmentStaffUserType.GovernmentStaffUserType", self.governmentusertype_id)


class StaffPersonalDetails(models.Model):
    # StaffcreationOfficeDetails.staff_unique_id (plain string, no DB relation;
    # always equal to this row's own staff_unique_id pk).
    staff_id = models.CharField(max_length=30, unique=True, db_column="staff_id")
    staff_unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        editable=False
    )
    marital_status = models.CharField(max_length=50, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    age = models.PositiveSmallIntegerField(blank=True, null=True)
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
        return f"Personal details for {getattr(self.staff, 'employee_name', self.staff_id)}"

    @property
    def staff(self):
        return ref_cache.get(StaffcreationOfficeDetails, self.staff_id)

    def save(self, *args, **kwargs):
        if self.staff_id and not self.staff_unique_id:
            self.staff_unique_id = self.staff_id
        super().save(*args, **kwargs)


# Backward compatibility alias
Staffcreation = StaffcreationOfficeDetails
