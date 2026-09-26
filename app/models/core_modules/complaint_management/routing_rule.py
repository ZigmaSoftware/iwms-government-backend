from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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

    category_id = models.CharField(db_index=True, max_length=30)
    subcategory_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
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
    priority_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    team_id = models.CharField(db_index=True, max_length=30)
    user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    sla_rule_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint Routing Rule"
        verbose_name_plural = "Complaint Routing Rules"

    def __str__(self):
        return f"Route {self.category_id} -> {self.team_id}"

    def _lookup(self, model_path, value):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, "unique_id")

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
    def team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.team_id,
        )

    @property
    def user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User", self.user_id
        )

    @property
    def sla_rule(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.sla_rule_master.ComplaintSlaRule",
            self.sla_rule_id,
        )
