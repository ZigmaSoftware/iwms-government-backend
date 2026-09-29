from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_sla_escalation_level_id():
    return f"CPTSLAL-{generate_unique_id()}"


class ComplaintSlaEscalationLevel(BaseMaster):
    """Resolution window for one level of the Staff Hierarchy.

    `level` matches `StaffHierarchy.hierarchy_level` (a top-of-chain role
    with no row of its own sits one above the roles reporting to it — see
    app/services/complaint_escalation.py). Only `is_enabled` rows take part:
    a ticket is first assigned to the lowest enabled level's staff, and on
    breach hops to the next enabled level above it — disabled levels (e.g.
    Driver, Operator) are skipped both as an entry point and as a hop target.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_sla_escalation_level_id,
        editable=False,
    )

    sla_rule_id = models.CharField(db_index=True, max_length=30)
    level = models.PositiveIntegerField(
        help_text="Staff Hierarchy level this window applies to (matches StaffHierarchy.hierarchy_level).",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether this hierarchy level participates in escalation for this SLA rule.",
    )
    resolve_within_minutes = models.IntegerField(
        help_text="Minutes this level has to resolve the ticket before it escalates further.",
    )

    class Meta:
        ordering = ["sla_rule_id", "level"]
        verbose_name = "Complaint SLA Escalation Level"
        verbose_name_plural = "Complaint SLA Escalation Levels"
        # One live row per (sla_rule_id, level) is enforced by
        # ComplaintSlaRuleSerializer — MySQL has no partial unique indexes,
        # and soft-deleted rows keep their (rule, level) pair.

    def __str__(self):
        return f"{self.sla_rule_id} L{self.level}: {self.resolve_within_minutes}m"

    @property
    def sla_rule(self):
        from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule

        return ref_cache.get(ComplaintSlaRule, self.sla_rule_id) if self.sla_rule_id else None
