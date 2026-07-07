from .priority_seeder import ComplaintPrioritySeeder
from .status_seeder import ComplaintStatusSeeder
from .source_seeder import ComplaintSourceSeeder
from .language_seeder import ComplaintLanguageSeeder
from .team_seeder import ComplaintTeamSeeder
from .module_seeder import ComplaintModuleSeeder
from .category_seeder import ComplaintCategorySeeder
from .subcategory_seeder import ComplaintSubcategorySeeder
from .sla_rule_seeder import ComplaintSlaRuleSeeder
from .routing_rule_seeder import ComplaintRoutingRuleSeeder
from .ticket_seeder import ComplaintTicketSeeder
from .feedback_seeder import ComplaintFeedbackSeeder

# Order matters: masters/rules before transactions, tickets before feedback.
COMPLAINT_TICKET_SEEDERS = [
    ComplaintPrioritySeeder,
    ComplaintStatusSeeder,
    ComplaintSourceSeeder,
    ComplaintLanguageSeeder,
    ComplaintTeamSeeder,
    ComplaintModuleSeeder,
    ComplaintCategorySeeder,
    ComplaintSubcategorySeeder,
    ComplaintSlaRuleSeeder,
    ComplaintRoutingRuleSeeder,
    ComplaintTicketSeeder,
    ComplaintFeedbackSeeder,
]
