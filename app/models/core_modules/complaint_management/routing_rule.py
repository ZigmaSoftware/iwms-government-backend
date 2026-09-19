from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule


def generate_routing_rule_id():
    return f"CPTRR-{generate_unique_id()}"


class ComplaintRoutingRule(BaseMaster):
    """Resolves a team/user/SLA for a ticket by category + geo + priority."""

    CACHE_SCOPES = ("complaint_routing_rule_list", "complaint_routing_rule_detail")

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
    # Optional flat geo scope: a rule may target a whole state/district or a
    # single local body. Empty fields mean "any". Plain CharFields holding
    # the related row's `unique_id` (no DB relation/join) — same convention
    # as Ward/CustomerCreation and the rest of the geo-hierarchy refactor.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
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
