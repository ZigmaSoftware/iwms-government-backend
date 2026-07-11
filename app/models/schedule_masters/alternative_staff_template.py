from django.db import models
from django.db.models import Max
from app.utils.comfun import generate_unique_id
from app.models.user_creations.staffcreation import Staffcreation
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat


def generate_alternative_staff_template_id():
    return f"ALTSTAFFTEMPLATE-{generate_unique_id()}"


class AlternativeStaffTemplate(models.Model):
    """
    Tracks temporary or permanent staff substitutions against
    a staff template with approval workflow and audit trail.
    """

    APPROVAL_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    # ------------------------------------------------------------------
    # CORE IDENTIFIER
    # ------------------------------------------------------------------

    unique_id = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_alternative_staff_template_id,
        editable=False
    )

    # ------------------------------------------------------------------
    # BUSINESS RELATIONSHIPS
    # ------------------------------------------------------------------

    staff_template = models.ForeignKey(
        'app.StaffTemplate',
        on_delete=models.PROTECT,
        db_column='staff_template_id',
        related_name='alternative_templates'
    )



    from_date = models.DateField(null=True, blank=True)
    to_date = models.DateField(null=True, blank=True)


    # effective_date = models.DateField()

    # ------------------------------------------------------------------
    # STAFF ASSIGNMENT
    # ------------------------------------------------------------------

    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="driver_id",
        to_field="staff_unique_id",
        related_name='alt_driver_templates'
    )

    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="operator_id",
        to_field="staff_unique_id",
        related_name='alt_operator_templates'
    )

    extra_operator_id = models.JSONField(
        default=list,
        blank=True,
        null=True,
        db_column='extra_operator_id',
        help_text="List of extra operator IDs"
    )

    # ------------------------------------------------------------------
    # GEO HIERARCHY (WHERE)
    # ------------------------------------------------------------------

    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alt_staff_templates",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    # ------------------------------------------------------------------
    # CHANGE JUSTIFICATION
    # ------------------------------------------------------------------

    change_reason = models.CharField(max_length=100)

    change_remarks = models.TextField(
        null=True,
        blank=True
    )

    # ------------------------------------------------------------------
    # APPROVAL WORKFLOW
    # ------------------------------------------------------------------

    # requested_by = models.ForeignKey(
    #     Staffcreation,
    #     on_delete=models.PROTECT,
    #     db_column='requested_by',
    #     related_name='alt_staff_requested'
    # )

    approved_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column='approved_by',
        related_name='alt_staff_approved',
        null=True,
        blank=True
    )

    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS_CHOICES,
        default='PENDING'
    )

    # ------------------------------------------------------------------
    # HUMAN READABLE CODE
    # ------------------------------------------------------------------

    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Example: RAVI-KART-01-ALT-01"
    )

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)

    # ------------------------------------------------------------------
    # META CONFIGURATION
    # ------------------------------------------------------------------

    class Meta:
        ordering = ['-created_at']

        indexes = [
            models.Index(fields=['staff_template']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['display_code']),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=['staff_template'],
                name='unique_staff_template_per_effective_date'
            )
        ]

    # ------------------------------------------------------------------
    # DISPLAY CODE GENERATION
    # ------------------------------------------------------------------

    def _generate_display_code(self):
        """
        Format:
        <DRIVER>-<OPERATOR>-<TEMPLATE_SEQ>-ALT-<ALT_SEQ>

        Example:
        VIKR-NAVE-01-ALT-01
        """

        def resolve_staff_name(staff, fallback):
            if not staff:
                return fallback
            if hasattr(staff, 'employee_name') and staff.employee_name:
                return staff.employee_name
            return fallback

        driver_name = resolve_staff_name(self.driver_id, "DRV")[:4].upper()
        operator_name = resolve_staff_name(self.operator_id, "OPR")[:4].upper()
        staff_base = f"{driver_name}-{operator_name}"

        matching_alt_templates = AlternativeStaffTemplate.objects.filter(
            display_code__startswith=f"{staff_base}-"
        )
        if self.pk:
            matching_alt_templates = matching_alt_templates.exclude(pk=self.pk)

        matching_alt_codes = matching_alt_templates.values_list(
            "display_code",
            flat=True,
        )

        existing_base_codes = []
        if self.staff_template:
            StaffTemplate = self.staff_template.__class__
            existing_base_codes.extend(
                StaffTemplate.objects
                .filter(display_code__startswith=f"{staff_base}-")
                .values_list("display_code", flat=True)
            )

        for code in matching_alt_codes:
            parts = str(code).split("-")
            if len(parts) >= 3:
                existing_base_codes.append("-".join(parts[:3]))

        base_seq = 0
        for code in existing_base_codes:
            parts = str(code).split("-")
            if len(parts) < 3:
                continue
            try:
                base_seq = max(base_seq, int(parts[2]))
            except ValueError:
                continue

        if base_seq == 0:
            base_seq = 1

        base_code = f"{staff_base}-{base_seq:02d}-ALT"

        matching_base_templates = AlternativeStaffTemplate.objects.filter(
            display_code__startswith=base_code
        )
        if self.pk:
            matching_base_templates = matching_base_templates.exclude(pk=self.pk)

        last_code = matching_base_templates.aggregate(
            max_code=Max("display_code")
        ).get("max_code")

        if last_code:
            try:
                last_seq = int(last_code.split("-")[-1])
            except (ValueError, IndexError):
                last_seq = 0
        else:
            last_seq = 0

        next_seq = last_seq + 1

        return f"{base_code}-{next_seq:02d}"

    # ------------------------------------------------------------------
    # SAVE OVERRIDE
    # ------------------------------------------------------------------

    def _staff_assignment_changed(self):
        if not self.pk:
            return False

        try:
            prev = (
                AlternativeStaffTemplate.objects
                .only("driver_id", "operator_id", "staff_template")
                .get(pk=self.pk)
            )
        except AlternativeStaffTemplate.DoesNotExist:
            return False

        return (
            prev.driver_id_id != self.driver_id_id
            or prev.operator_id_id != self.operator_id_id
            or prev.staff_template_id != self.staff_template_id
        )

    def save(self, *args, **kwargs):

        if not self.display_code or self._staff_assignment_changed():
            self.display_code = self._generate_display_code()

        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # STRING REPRESENTATION
    # ------------------------------------------------------------------

    def __str__(self):
        return self.display_code
