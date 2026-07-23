from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat



# ------------------------------------------------------------------
# SYSTEM UNIQUE ID (Machine-readable)
# ------------------------------------------------------------------
def generate_stafftemplate_id():
    return f"STFTEMP-{generate_unique_id(length=6)}"

class StaffTemplate(BaseMaster):
    
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

    # ---------------- DRIVER ROLE ----------------
    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="driver_templates",
        db_column="driver_id",
        to_field="staff_unique_id"
    )

    # ---------------- OPERATOR ROLE ----------------
    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="operator_templates",
        db_column="operator_id",
        to_field="staff_unique_id"
    )

    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        help_text="List of additional operator unique IDs"
    )

    # ---------------- GEO HIERARCHY (WHERE) ----------------
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_templates",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    # ---------------- HUMAN READABLE BUSINESS CODE ----------------
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Supervisor friendly identifier (e.g. RAVI-KART-01)"
    )

    # ---------------- AUDIT FIELDS ----------------
    approved_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="stafftemplate_approved",
        db_column="approved_by",
        to_field="staff_unique_id",
        null=True,
        blank=True
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

        driver_name = resolve_staff_name(self.driver_id, "DRV")[:4].upper()
        operator_name = resolve_staff_name(self.operator_id, "OPR")[:4].upper()

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
