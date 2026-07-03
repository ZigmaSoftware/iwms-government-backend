from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.status_master import ComplaintStatus


class ComplaintStatusSeeder(BaseSeeder):
    name = "complaint_status"

    # (status_code, status_name, is_final, allow_reopen, sort_order)
    STATUSES = [
        ("SUBMITTED", "Submitted", False, False, 10),
        ("ASSIGNED", "Assigned", False, False, 20),
        ("IN_PROGRESS", "In Progress", False, False, 30),
        ("ESCALATED", "Escalated", False, False, 35),
        ("RESOLVED", "Resolved", False, True, 40),
        ("REOPENED", "Reopened", False, False, 45),
        ("CLOSED", "Closed", True, False, 50),
        ("REJECTED", "Rejected", True, False, 60),
        ("CANCELLED", "Cancelled", True, False, 70),
    ]

    def run(self):
        for code, name, is_final, allow_reopen, sort_order in self.STATUSES:
            ComplaintStatus.objects.get_or_create(
                status_code=code,
                defaults={
                    "status_name": name,
                    "is_final": is_final,
                    "allow_reopen": allow_reopen,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint statuses seeded ({len(self.STATUSES)} records)---")
