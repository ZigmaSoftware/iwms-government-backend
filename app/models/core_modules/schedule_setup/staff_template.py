from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils import ref_cache



# ------------------------------------------------------------------
# SYSTEM UNIQUE ID (Machine-readable)
# ------------------------------------------------------------------
def generate_stafftemplate_id():
    return f"STFTEMP-{generate_unique_id(length=6)}"

class StaffTemplate(BaseMaster):

    CACHE_SCOPES = (
        "staff_template_list",
        "staff_template_detail",
        "trip_plan_list",
        "trip_plan_detail",
        "alternative_staff_template_list",
        "alternative_staff_template_detail",
    )

    # AlternativeStaffTemplate is deliberately excluded: it has no is_deleted
    # field (not soft-deletable) — see app/utils/cascade_delete.py. Everything
    # under trip_plans/daily_trip_assignments cascades further via their own
    # CASCADE_SOFT_DELETE declarations.
    CASCADE_SOFT_DELETE = ("trip_plans", "daily_trip_assignments")

    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"


    unique_id = models.CharField(
        max_length=20,
        primary_key=True,
        default=generate_stafftemplate_id,
        editable=False
    )

    # ---------------- DRIVER / OPERATOR ROLES ----------------
    # Plain staff_unique_ids (no DB relation); the `driver` / `operator`
    # properties below resolve the staff rows.
    driver_id = models.CharField(max_length=30, db_column="driver_id", db_index=True)
    operator_id = models.CharField(max_length=30, db_column="operator_id", db_index=True)

    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        help_text="List of additional operator unique IDs"
    )

    # ---------------- GEO HIERARCHY (WHERE) ----------------
    # Plain CharFields holding the related row's `unique_id` (no DB
    # relation/join) — literal "_id"-suffixed field names, matching the rest
    # of the geo-hierarchy (Continent/.../Panchayat, Ward, CustomerCreation).
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    # ---------------- HUMAN READABLE BUSINESS CODE ----------------
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Supervisor friendly identifier (e.g. RAVI-KART-01)"
    )

    # ---------------- AUDIT FIELDS ----------------
    approved_by_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="approved_by", db_index=True
    )

    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING
    )


    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------------- META ----------------
    class Meta:
        indexes = [
            models.Index(fields=["status", "approval_status"]),
            models.Index(fields=["display_code"]),
        ]
        ordering = ["-created_at"]

    # ------------------------------------------------------------------
    # PLAIN-STRING STAFF LOOKUPS
    # ------------------------------------------------------------------
    def _staff(self, staff_unique_id):
        return ref_cache.get(Staffcreation, staff_unique_id, "staff_unique_id")

    @property
    def driver(self):
        return self._staff(self.driver_id)

    @property
    def operator(self):
        return self._staff(self.operator_id)

    @property
    def approved_by(self):
        return self._staff(self.approved_by_id)

    @property
    def alternative_templates(self):
        """AlternativeStaffTemplate rows for this template (plain
        staff_template_id, no DB relation)."""
        from app.models.core_modules.schedule_setup.alternative_staff_template import (
            AlternativeStaffTemplate,
        )

        return AlternativeStaffTemplate.objects.filter(staff_template_id=self.unique_id)

    # ------------------------------------------------------------------
    # DISPLAY CODE GENERATION (Enterprise Safe)
    # ------------------------------------------------------------------
    def _generate_display_code(self):
        """
        Format: <DRIVER>-<OPERATOR>-<SEQ>
        Example: RAVI-KART-01
        """

        def resolve_staff_name(staff, fallback):
            if not staff:
                return fallback
            if hasattr(staff, 'employee_name') and staff.employee_name:
                return staff.employee_name
            return fallback

        driver_name = resolve_staff_name(self.driver, "DRV")[:4].upper()
        operator_name = resolve_staff_name(self.operator, "OPR")[:4].upper()

        base_code = f"{driver_name}-{operator_name}"

        # Find highest existing sequence
        last_code = (
            StaffTemplate.objects
            .filter(display_code__startswith=base_code)
            .aggregate(max_code=Max("display_code"))
            .get("max_code")
        )

        if last_code:
            try:
                last_seq = int(last_code.split("-")[-1])
            except ValueError:
                last_seq = 0
        else:
            last_seq = 0

        next_seq = last_seq + 1
        return f"{base_code}-{next_seq:02d}"

    # ------------------------------------------------------------------
    # OVERRIDE SAVE
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.display_code:
            self.display_code = self._generate_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_code
