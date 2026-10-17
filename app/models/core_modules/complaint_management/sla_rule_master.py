from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_sla_rule_id():
    return f"CPTSLA-{generate_unique_id()}"


class ComplaintSlaRule(BaseMaster):
    """Escalation timing per category/priority/source (and area).

    Escalation windows live in `ComplaintSlaEscalationLevel` rows (one per
    Staff Hierarchy level) — see `escalation_levels`.

    A rule can be scoped to a place — state, district, area type and/or one
    local body — the same way Staff Hierarchy rows are, so one complaint type
    can escalate on different levels/timings in, say, Anthiyur Panchayat and
    Chennai Corporation. Blank scope columns mean "everywhere"; for a ticket
    the rule with the deepest scope covering its area wins (see
    app/utils/complaint_ticket_routing.py).
    """

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

    # Counts only 09:00-18:00 Mon-Sat when adding the escalation windows.
    working_hours_only = models.BooleanField(default=False)

    # Scope (plain unique_id strings, no DB relation), broadest first. At
    # most one local-body column is set; parents are stored filled in.
    country_id = models.CharField(max_length=30, null=True, blank=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

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
    def escalation_levels(self):
        """Live per-level escalation windows, lowest level first."""
        from app.models.core_modules.complaint_management.sla_escalation_level import (
            ComplaintSlaEscalationLevel,
        )

        return ComplaintSlaEscalationLevel.objects.filter(
            sla_rule_id=self.unique_id, is_deleted=False
        ).order_by("level")
