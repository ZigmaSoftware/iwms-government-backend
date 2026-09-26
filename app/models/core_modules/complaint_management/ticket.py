from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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

    source_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    customer_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    wa_phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    profile_name = models.CharField(max_length=150, null=True, blank=True)
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("transgender", "Transgender"),
    ]
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    language_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)

    category_id = models.CharField(db_index=True, max_length=30)
    # WasteType unique_ids (plain JSON list, no join table); read via `waste_types`.
    waste_type_ids = models.JSONField(default=list, blank=True)
    subcategory_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    priority_id = models.CharField(db_index=True, max_length=30)
    status_id = models.CharField(db_index=True, max_length=30)

    title = models.CharField(max_length=250, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    location_text = models.TextField(blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    # Flat geo hierarchy: plain CharFields holding the related row's
    # `unique_id` (no DB relation/join) — same convention as Ward/
    # CustomerCreation and the rest of the geo-hierarchy refactor.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    # Only one of the local-body fields below should be populated at a time -
    # it is the ticket's "city" (the level right below District).
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

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
        field - the ticket's "city" - or (None, None, None). Resolves the
        stored unique_id string against its owning master."""
        from app.utils.hierarchy import _resolve_geo_candidate

        for field, name_attr in self.LOCAL_BODY_FIELDS:
            obj = _resolve_geo_candidate(self, field)
            if obj:
                return field, obj, getattr(obj, name_attr, None)
        return None, None, None

    assigned_team_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    assigned_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    assigned_staff_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)

    sla_due_at = models.DateTimeField(null=True, blank=True)
    first_response_due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    sla_breached = models.BooleanField(default=False)
    sla_breached_at = models.DateTimeField(null=True, blank=True)

    reopened_count = models.IntegerField(default=0)
    parent_ticket_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
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

    # =============================
    # PLAIN-STRING RELATION LOOKUPS
    # =============================
    # All relation columns above are plain unique_id strings (no DB
    # relation), same as Ward/CustomerCreation. Properties below resolve
    # them so existing `ticket.<name>` attribute access keeps working.
    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def source(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.source_master.ComplaintSource",
            self.source_id,
        )

    @property
    def customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.customer_id,
        )

    @property
    def language(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.language_master.ComplaintLanguage",
            self.language_id,
        )

    @property
    def category(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.category_master.ComplaintCategory",
            self.category_id,
        )

    @property
    def subcategory(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.subcategory_master.ComplaintSubcategory",
            self.subcategory_id,
        )

    @property
    def priority(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.priority_master.ComplaintPriority",
            self.priority_id,
        )

    @property
    def status(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.status_master.ComplaintStatus",
            self.status_id,
        )

    @property
    def assigned_team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.assigned_team_id,
        )

    @property
    def assigned_user(self):
        return self._lookup("app.models.superadmin_masters.auth_user.User", self.assigned_user_id)

    @property
    def assigned_staff(self):
        return self._lookup(
            "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails",
            self.assigned_staff_id,
            field="staff_unique_id",
        )

    @property
    def parent_ticket(self):
        if not self.parent_ticket_id:
            return None
        return type(self).objects.filter(unique_id=self.parent_ticket_id).first()

    @property
    def child_tickets(self):
        return type(self).objects.filter(parent_ticket_id=self.unique_id)

    @property
    def assignment_history(self):
        """Reverse helper replacing the old `related_name` (history.ticket_id
        is now a plain unique_id string)."""
        from app.models.core_modules.complaint_management.assignment_history import (
            ComplaintAssignmentHistory,
        )

        return ComplaintAssignmentHistory.objects.filter(ticket_id=self.unique_id)

    @property
    def comments(self):
        """Reverse helper replacing the old `related_name` (comment.ticket_id
        is now a plain unique_id string)."""
        from app.models.core_modules.complaint_management.comment import (
            ComplaintComment,
        )

        return ComplaintComment.objects.filter(ticket_id=self.unique_id)

    @property
    def escalation_history(self):
        """Reverse helper replacing the old `related_name`
        (history.ticket_id is now a plain unique_id string)."""
        from app.models.core_modules.complaint_management.escalation_history import (
            ComplaintEscalationHistory,
        )

        return ComplaintEscalationHistory.objects.filter(ticket_id=self.unique_id)

    @property
    def status_history(self):
        """Reverse helper replacing the old `related_name`
        (history.ticket_id is now a plain unique_id string)."""
        from app.models.core_modules.complaint_management.status_history import (
            ComplaintStatusHistory,
        )

        return ComplaintStatusHistory.objects.filter(ticket_id=self.unique_id)

    @property
    def attachments(self):
        """Reverse helper replacing the old `related_name`
        (attachment.ticket_id is now a plain unique_id string)."""
        from app.models.core_modules.complaint_management.ticket_attachment import (
            ComplaintAttachment,
        )

        return ComplaintAttachment.objects.filter(ticket_id=self.unique_id)

    @property
    def waste_types(self):
        from app.models.masters.waste_masters.wastetype import WasteType

        return WasteType.objects.filter(unique_id__in=self.waste_type_ids or [])

    @property
    def extra_details(self):
        """Reverse helper replacing the old `related_name`
        (detail.ticket_id is now a plain unique_id string)."""
        from app.models.core_modules.complaint_management.ticket_extra_detail import (
            ComplaintTicketExtraDetail,
        )

        return ComplaintTicketExtraDetail.objects.filter(ticket_id=self.unique_id)
