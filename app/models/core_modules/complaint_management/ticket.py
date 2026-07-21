from django.conf import settings
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
from app.models.core_modules.complaint_management.source_master import ComplaintSource
from app.models.core_modules.complaint_management.language_master import ComplaintLanguage
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.team_master import ComplaintTeam


def generate_ticket_unique_id():
    return f"CPTTKT-{generate_unique_id()}"


def generate_ticket_no():
    """Sequential ticket number IWMS-<seq:06d> based on max existing ticket_no."""
    last = ComplaintTicket.objects.aggregate(max_no=Max("ticket_no"))["max_no"]
    last_num = 0
    if last:
        try:
            last_num = int(str(last).split("-")[-1])
        except (ValueError, IndexError):
            last_num = 0
    return f"IWMS-{last_num + 1:06d}"


class ComplaintTicket(BaseMaster):
    """Main complaint ticket. Citizen = CustomerCreation; geo = flat
    State/District/local-body FKs (same pattern as CustomerCreation and
    StaffcreationOfficeDetails)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_ticket_unique_id,
        editable=False,
    )
    ticket_no = models.CharField(
        max_length=50,
        unique=True,
        default=generate_ticket_no,
        editable=False,
    )

    source = models.ForeignKey(
        ComplaintSource,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
    )
    wa_phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    profile_name = models.CharField(max_length=150, null=True, blank=True)
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("transgender", "Transgender"),
    ]
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    language = models.ForeignKey(
        ComplaintLanguage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    waste_types = models.ManyToManyField(
        "app.WasteType",
        blank=True,
        related_name="complaint_tickets",
    )
    subcategory = models.ForeignKey(
        ComplaintSubcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        related_name="tickets",
    )

    title = models.CharField(max_length=250, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    location_text = models.TextField(blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="area_type_id",
    )
    # Only one of the local-body FKs below should be populated at a time -
    # it is the ticket's "city" (the level right below District).
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        db_column="panchayat_id",
    )

    LOCAL_BODY_FIELDS = (
        ("corporation", "corporation_name"),
        ("municipality", "municipality_name"),
        ("town_panchayat", "town_panchayat_name"),
        ("panchayat_union", "union_name"),
        ("panchayat", "panchayat_name"),
    )

    @property
    def local_body(self):
        """(field_name, instance, display_name) of the populated local-body
        FK - the ticket's "city" - or (None, None, None)."""
        for field, name_attr in self.LOCAL_BODY_FIELDS:
            obj = getattr(self, field, None)
            if obj:
                return field, obj, getattr(obj, name_attr, None)
        return None, None, None

    assigned_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaint_tickets",
    )
    assigned_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaint_tickets_staff",
    )

    sla_due_at = models.DateTimeField(null=True, blank=True)
    first_response_due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    sla_breached = models.BooleanField(default=False)
    sla_breached_at = models.DateTimeField(null=True, blank=True)

    reopened_count = models.IntegerField(default=0)
    parent_ticket = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_tickets",
    )
    # Not DB-unique: the public grievance duplicate check only rejects a
    # resubmission within the 6-hour cooldown window, so the same device can
    # legitimately produce more than one row with this key over time.
    idempotency_key = models.CharField(max_length=150, db_index=True, null=True, blank=True)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Ticket"
        verbose_name_plural = "Complaint Tickets"
        indexes = [
            models.Index(fields=["ticket_no"]),
            models.Index(fields=["wa_phone"]),
            models.Index(fields=["sla_due_at"]),
        ]

    def __str__(self):
        return self.ticket_no
