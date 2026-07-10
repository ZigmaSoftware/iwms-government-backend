from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.module_master import ComplaintModule


class ComplaintModuleSeeder(BaseSeeder):
    name = "complaint_module"

    # (module_code, module_name, sort_order)
    MODULES = [
        ("GENERAL", "General / Other", 0),
        ("ASSETS", "Assets (Bins & Collection Points)", 10),
        ("TRANSPORT", "Transport & Vehicles", 20),
        ("SCHEDULE", "Collection Schedule", 30),
        ("CUSTOMER_SERVICE", "Customer Service", 40),
        ("WASTE_TYPES", "Waste Types", 50),
    ]

    def run(self):
        for code, name, sort_order in self.MODULES:
            ComplaintModule.objects.get_or_create(
                module_code=code,
                defaults={
                    "module_name": name,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint modules seeded ({len(self.MODULES)} records)---")
