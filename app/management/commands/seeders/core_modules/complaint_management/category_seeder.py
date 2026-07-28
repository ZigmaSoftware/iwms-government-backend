from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.core_modules.complaint_management.module_master import ComplaintModule


class ComplaintCategorySeeder(BaseSeeder):
    name = "complaint_category"

    # (category_code, category_name, default_priority_code, default_team_code, module_code,
    #  requires_location, requires_media, requires_address_change_detail, sort_order)
    CATEGORIES = [
        ("MISSED_PICKUP", "Missed Pickup", "P2", "SANITATION", "SCHEDULE", True, False, False, 10),
        ("BULK_WASTE", "Bulk Waste Pickup", "P3", "SANITATION", "SCHEDULE", True, True, False, 20),
        ("WORKER_CONDUCT", "Worker Conduct", "P2", "SANITATION_L2", "GENERAL", False, False, False, 30),
        ("VEHICLE_ISSUE", "Vehicle Issue", "P3", "SANITATION", "TRANSPORT", True, True, False, 40),
        ("BILLING_QUERY", "Billing Inquiry", "P3", "BILLING", "CUSTOMER_SERVICE", False, False, False, 50),
        ("ADDRESS_CHANGE", "Change of Address", "P3", "ADDRESS_DESK", "CUSTOMER_SERVICE", False, False, True, 60),
        ("OTHER", "Other", "P4", "GENERAL", "GENERAL", False, False, False, 70),
        # Civic complaint types offered on the public grievance form (GCC-style
        # Public Grievance & Redressal taxonomy).
        ("AIR_QUALITY", "Air Quality", "P3", "GENERAL", "GENERAL", True, False, False, 110),
        ("BUILDING_PLAN", "Building Plan Permission", "P4", "GENERAL", "GENERAL", True, False, False, 120),
        ("FLOOD", "Flood", "P1", "GENERAL", "GENERAL", True, False, False, 130),
        ("GARBAGE", "Garbage", "P2", "SANITATION", "GENERAL", True, False, False, 140),
        ("GENERAL_COMPLAINT", "General", "P4", "GENERAL", "GENERAL", False, False, False, 150),
        ("MEGA_STREETS_CONSTRUCTION", "Mega Streets - Construction Phase", "P3", "GENERAL", "GENERAL", True, False, False, 160),
        ("MEGA_STREETS_OPERATION", "Mega Streets - Operation Phase", "P3", "GENERAL", "GENERAL", True, False, False, 170),
        ("MEGA_STREETS_PLANNING", "Mega Streets - Planning Phase", "P3", "GENERAL", "GENERAL", True, False, False, 180),
        ("PARK_PLAYGROUND", "Park and Playground", "P3", "GENERAL", "GENERAL", True, False, False, 190),
        ("PUBLIC_HEALTH", "Public Health", "P2", "GENERAL", "GENERAL", True, False, False, 200),
        ("PUBLIC_TOILET", "Public Toilet", "P2", "SANITATION", "GENERAL", True, False, False, 210),
        ("ROAD_FOOTPATH", "Road and Footpath", "P3", "GENERAL", "GENERAL", True, False, False, 220),
        ("STORM_WATER_DRAIN", "Storm Water Drains", "P2", "GENERAL", "GENERAL", True, False, False, 230),
        ("STREET_LIGHT", "Street Light", "P3", "GENERAL", "GENERAL", True, False, False, 240),
        ("TAX_LICENCE", "Tax and Licence", "P4", "BILLING", "CUSTOMER_SERVICE", False, False, False, 250),
        ("VOTER_ID", "Voter ID", "P4", "GENERAL", "GENERAL", False, False, False, 260),
        ("WATER_STAGNATION", "Water Stagnation", "P2", "SANITATION", "GENERAL", True, False, False, 270),
    ]

    def run(self):
        for code, name, priority_code, team_code, module_code, req_loc, req_media, req_addr, sort_order in self.CATEGORIES:
            priority = ComplaintPriority.objects.filter(priority_code=priority_code).first()
            team = ComplaintTeam.objects.filter(team_code=team_code).first()
            module = ComplaintModule.objects.filter(module_code=module_code).first()
            ComplaintCategory.objects.get_or_create(
                category_code=code,
                defaults={
                    "category_name": name,
                    "default_priority": priority,
                    "default_team": team,
                    "module": module,
                    "requires_location": req_loc,
                    "requires_media": req_media,
                    "requires_address_change_detail": req_addr,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        # Keep the public-form dropdown alphabetical regardless of when a
        # category was added (mirrors the GCC PGR complaint-type list).
        for index, category in enumerate(
            ComplaintCategory.objects.filter(is_deleted=False).order_by("category_name")
        ):
            new_order = (index + 1) * 10
            if category.sort_order != new_order:
                category.sort_order = new_order
                category.save(update_fields=["sort_order"])

        self.log(f"---Complaint categories seeded ({len(self.CATEGORIES)} records)---")
