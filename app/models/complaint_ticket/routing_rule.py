from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.subcategory_master import ComplaintSubcategory
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.team_master import ComplaintTeam
from app.models.complaint_ticket.sla_rule_master import ComplaintSlaRule


def generate_routing_rule_id():
    return f"CPTRR-{generate_unique_id()}"


class ComplaintRoutingRule(BaseMaster):
    """Resolves a team/user/SLA for a ticket by category + geo + priority."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_routing_rule_id,
        editable=False,
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="routing_rules",
    )
    subcategory = models.ForeignKey(
        ComplaintSubcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    location_node = models.ForeignKey(
        HierarchyNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
        to_field="unique_id",
        db_column="location_node_id",
    )
    priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.PROTECT,
        related_name="routing_rules",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_routing_rules",
    )
    sla_rule = models.ForeignKey(
        ComplaintSlaRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routing_rules",
    )

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint Routing Rule"
        verbose_name_plural = "Complaint Routing Rules"

    def __str__(self):
        return f"Route {self.category_id} -> {self.team_id}"
