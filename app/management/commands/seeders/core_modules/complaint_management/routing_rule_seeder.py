from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule
from app.models.core_modules.complaint_management.routing_rule import ComplaintRoutingRule


class ComplaintRoutingRuleSeeder(BaseSeeder):
    name = "complaint_routing_rule"

    def run(self):
        total = 0
        for category in ComplaintCategory.objects.filter(is_deleted=False):
            if not category.default_team:
                self.log(f"Category '{category.category_code}' has no default team - skipping routing rule.")
                continue
            sla_rule = ComplaintSlaRule.objects.filter(
                category_id=category.unique_id, subcategory_id__isnull=True, is_deleted=False
            ).first()
            ComplaintRoutingRule.objects.get_or_create(
                category_id=category.unique_id,
                subcategory_id=None,
                state_id=None,
                district_id=None,
                priority_id=None,
                defaults={
                    "team_id": category.default_team_id,
                    "sla_rule_id": sla_rule.unique_id if sla_rule else None,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint routing rules seeded ({total} records)---")
