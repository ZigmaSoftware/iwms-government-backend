from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.subcategory_master import ComplaintSubcategory


class ComplaintSubcategorySeeder(BaseSeeder):
    name = "complaint_subcategory"

    # (category_code, subcategory_code, subcategory_name, sort_order)
    SUBCATEGORIES = [
        ("MISSED_PICKUP", "NOT_COLLECTED", "Not Collected Today", 10),
        ("MISSED_PICKUP", "PARTIAL_COLLECTION", "Partial Collection", 20),
        ("BULK_WASTE", "FURNITURE", "Furniture Pickup", 10),
        ("BULK_WASTE", "CONSTRUCTION_DEBRIS", "Construction Debris", 20),
        ("WORKER_CONDUCT", "BEHAVIOUR", "Worker Behaviour", 10),
        ("VEHICLE_ISSUE", "VEHICLE_NO_SHOW", "Vehicle Did Not Arrive", 10),
        ("VEHICLE_ISSUE", "VEHICLE_DAMAGE", "Vehicle Caused Damage", 20),
        ("BILLING_QUERY", "OVERCHARGE", "Overcharge / Incorrect Bill", 10),
        ("BILLING_QUERY", "PAYMENT_NOT_REFLECTED", "Payment Not Reflected", 20),
        ("ADDRESS_CHANGE", "SERVICE_ADDRESS", "Service Address Change", 10),
        ("ADDRESS_CHANGE", "BILLING_ADDRESS", "Billing Address Change", 20),
    ]

    def run(self):
        total = 0
        for category_code, sub_code, sub_name, sort_order in self.SUBCATEGORIES:
            category = ComplaintCategory.objects.filter(category_code=category_code).first()
            if not category:
                self.log(f"ComplaintCategory '{category_code}' not found - skipping.")
                continue
            ComplaintSubcategory.objects.get_or_create(
                category=category,
                subcategory_code=sub_code,
                defaults={
                    "subcategory_name": sub_name,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1
        self.log(f"---Complaint subcategories seeded ({total} records)---")
