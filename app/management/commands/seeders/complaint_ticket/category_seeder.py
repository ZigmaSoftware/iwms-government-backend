from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.team_master import ComplaintTeam


class ComplaintCategorySeeder(BaseSeeder):
    name = "complaint_category"

    # (category_code, category_name, default_priority_code, default_team_code,
    #  requires_location, requires_media, requires_address_change_detail, sort_order)
    CATEGORIES = [
        ("MISSED_PICKUP", "Missed Pickup", "P2", "SANITATION", True, False, False, 10),
        ("BULK_WASTE", "Bulk Waste Pickup", "P3", "SANITATION", True, True, False, 20),
        ("WORKER_CONDUCT", "Worker Conduct", "P2", "SANITATION_L2", False, False, False, 30),
        ("VEHICLE_ISSUE", "Vehicle Issue", "P3", "SANITATION", True, True, False, 40),
        ("BILLING_QUERY", "Billing Inquiry", "P3", "BILLING", False, False, False, 50),
        ("ADDRESS_CHANGE", "Change of Address", "P3", "ADDRESS_DESK", False, False, True, 60),
        ("OTHER", "Other", "P4", "GENERAL", False, False, False, 70),
    ]

    def run(self):
        for code, name, priority_code, team_code, req_loc, req_media, req_addr, sort_order in self.CATEGORIES:
            priority = ComplaintPriority.objects.filter(priority_code=priority_code).first()
            team = ComplaintTeam.objects.filter(team_code=team_code).first()
            ComplaintCategory.objects.get_or_create(
                category_code=code,
                defaults={
                    "category_name": name,
                    "default_priority": priority,
                    "default_team": team,
                    "requires_location": req_loc,
                    "requires_media": req_media,
                    "requires_address_change_detail": req_addr,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint categories seeded ({len(self.CATEGORIES)} records)---")
