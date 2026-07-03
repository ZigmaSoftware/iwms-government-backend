from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.subcategory_master import ComplaintSubcategory
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.source_master import ComplaintSource
from app.models.complaint_ticket.team_master import ComplaintTeam


def generate_sla_rule_id():
    return f"CPTSLA-{generate_unique_id()}"


class ComplaintSlaRule(BaseMaster):
    """Configurable assign/resolve SLA + escalation per category/priority/source."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_sla_rule_id,
        editable=False,
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="sla_rules",
    )
    subcategory = models.ForeignKey(
        ComplaintSubcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sla_rules",
    )
    priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.PROTECT,
        related_name="sla_rules",
    )
    source = models.ForeignKey(
        ComplaintSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sla_rules",
    )

    assign_within_minutes = models.IntegerField(null=True, blank=True)
    resolve_within_minutes = models.IntegerField(null=True, blank=True)
    working_hours_only = models.BooleanField(default=False)
    escalation_after_minutes = models.IntegerField(null=True, blank=True)
    escalation_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_sla_rules",
    )

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint SLA Rule"
        verbose_name_plural = "Complaint SLA Rules"

    def __str__(self):
        return f"SLA {self.category_id} / {self.priority_id}"
