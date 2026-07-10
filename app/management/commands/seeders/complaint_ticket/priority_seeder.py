from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.priority_master import ComplaintPriority


class ComplaintPrioritySeeder(BaseSeeder):
    name = "complaint_priority"

    PRIORITIES = [
        ("P1", "Emergency", 10),
        ("P2", "High", 20),
        ("P3", "Normal", 30),
        ("P4", "Info", 40),
    ]

    def run(self):
        for code, name, sort_order in self.PRIORITIES:
            ComplaintPriority.objects.get_or_create(
                priority_code=code,
                defaults={
                    "priority_name": name,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint priorities seeded ({len(self.PRIORITIES)} records)---")
