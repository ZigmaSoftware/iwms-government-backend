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
                category=category, subcategory__isnull=True, is_deleted=False
            ).first()
            ComplaintRoutingRule.objects.get_or_create(
                category=category,
                subcategory=None,
                state=None,
                district=None,
                priority=None,
                defaults={
                    "team": category.default_team,
                    "sla_rule": sla_rule,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint routing rules seeded ({total} records)---")
