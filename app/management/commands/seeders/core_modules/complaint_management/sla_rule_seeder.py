from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.sla_escalation_level import ComplaintSlaEscalationLevel
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule
from app.services.complaint_escalation import hierarchy_level_options
from app.utils.staff_hierarchy import SCOPE_FIELDS


class ComplaintSlaRuleSeeder(BaseSeeder):
    name = "complaint_sla_rule"

    # One default SLA rule per category, keyed off the category's own default
    # priority, with this many minutes at each escalation level.
    PRIORITY_LEVEL_MINUTES = {
        "P1": 60,
        "P2": 360,
        "P3": 1440,
        "P4": 2880,
    }
    DEFAULT_LEVEL_MINUTES = 1440

    # Field roles don't own grievances: levels made up only of these are
    # seeded disabled, so tickets start at the supervisor tier.
    NON_ENTRY_ROLE_SUFFIXES = ("_driver", "_operator")

    def run(self):
        total = 0
        for category in ComplaintCategory.objects.filter(is_deleted=False):
            priority = category.default_priority
            if not priority:
                self.log(f"Category '{category.category_code}' has no default priority - skipping SLA rule.")
                continue
            ComplaintSlaRule.objects.get_or_create(
                category_id=category.unique_id,
                subcategory_id=None,
                priority_id=priority.unique_id,
                source_id=None,
                # The seeded default applies everywhere; area-specific rules
                # are configured on the SLA Rules screen.
                **{field: None for field in SCOPE_FIELDS},
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint SLA rules seeded ({total} records)---")
        self._seed_escalation_levels()

    def _seed_escalation_levels(self):
        """Give every SLA rule that has no escalation levels yet one window
        per Staff Hierarchy level. Rules already configured are left alone."""
        seeded = 0
        for rule in ComplaintSlaRule.objects.filter(is_deleted=False):
            if rule.escalation_levels.exists():
                continue
            # A scoped rule gets the levels of the chain that applies there.
            scope = {field: getattr(rule, field) for field in SCOPE_FIELDS if getattr(rule, field)}
            levels = hierarchy_level_options(scope or None)
            if not levels:
                continue
            minutes = self.PRIORITY_LEVEL_MINUTES.get(
                getattr(rule.priority, "priority_code", None), self.DEFAULT_LEVEL_MINUTES
            )
            ComplaintSlaEscalationLevel.objects.bulk_create(
                ComplaintSlaEscalationLevel(
                    sla_rule_id=rule.unique_id,
                    level=option["level"],
                    is_enabled=not all(
                        role["name"].endswith(self.NON_ENTRY_ROLE_SUFFIXES) for role in option["roles"]
                    ),
                    resolve_within_minutes=minutes,
                )
                for option in levels
            )
            seeded += 1
        self.log(f"---SLA escalation levels seeded for {seeded} rule(s)---")
