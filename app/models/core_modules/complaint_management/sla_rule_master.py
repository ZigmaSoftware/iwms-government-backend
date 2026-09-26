from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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

    category_id = models.CharField(db_index=True, max_length=30)
    subcategory_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    priority_id = models.CharField(db_index=True, max_length=30)
    source_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)

    assign_within_minutes = models.IntegerField(null=True, blank=True)
    resolve_within_minutes = models.IntegerField(null=True, blank=True)
    working_hours_only = models.BooleanField(default=False)
    escalation_after_minutes = models.IntegerField(null=True, blank=True)
    escalation_team_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Complaint SLA Rule"
        verbose_name_plural = "Complaint SLA Rules"

    def __str__(self):
        return f"SLA {self.category_id} / {self.priority_id}"

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
    def source(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.source_master.ComplaintSource",
            self.source_id,
        )

    @property
    def escalation_team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.escalation_team_id,
        )
