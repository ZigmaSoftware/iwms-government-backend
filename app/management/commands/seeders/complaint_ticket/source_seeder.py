from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.source_master import ComplaintSource


class ComplaintSourceSeeder(BaseSeeder):
    name = "complaint_source"

    SOURCES = [
        ("WHATSAPP", "WhatsApp"),
        ("MOBILE_APP", "Mobile App"),
        ("WEB", "Web Portal"),
        ("CALL_CENTER", "Call Center"),
        ("ADMIN", "Admin"),
    ]

    def run(self):
        for code, name in self.SOURCES:
            ComplaintSource.objects.get_or_create(
                source_code=code,
                defaults={
                    "source_name": name,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint sources seeded ({len(self.SOURCES)} records)---")
