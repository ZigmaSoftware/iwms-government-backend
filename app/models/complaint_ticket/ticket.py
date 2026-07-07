from django.conf import settings
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
from app.models.complaint_ticket.source_master import ComplaintSource
from app.models.complaint_ticket.language_master import ComplaintLanguage
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.subcategory_master import ComplaintSubcategory
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.status_master import ComplaintStatus
from app.models.complaint_ticket.team_master import ComplaintTeam


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
    """Main complaint ticket. Citizen = CustomerCreation; geo = HierarchyNode."""

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
    profile_name = models.CharField(max_length=150, null=True, blank=True)
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
    location_node = models.ForeignKey(
        HierarchyNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_tickets",
        to_field="unique_id",
        db_column="location_node_id",
    )

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
    idempotency_key = models.CharField(max_length=150, unique=True, null=True, blank=True)
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
