from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory


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
        # ---- Civic complaint sub-types for the public grievance form ----
        # Garbage (mirrors the GCC PGR sub-type list)
        ("GARBAGE", "REMOVAL_OF_GARBAGE", "Removal of Garbage", 10),
        ("GARBAGE", "OVERFLOWING_BIN", "Overflowing of Garbage Bin", 20),
        ("GARBAGE", "REMOVAL_OF_DEBRIS", "Removal of Debris", 30),
        ("GARBAGE", "ABSENTEEISM_SWEEPERS", "Absenteeism of Sweepers", 40),
        ("GARBAGE", "ABSENTEEISM_D2D_COLLECTOR", "Absenteeism of Door to Door Garbage Collector", 50),
        ("GARBAGE", "IMPROPER_SWEEPING", "Improper Sweeping", 60),
        ("GARBAGE", "PROVISION_OF_BIN", "Provision of Garbage Bin", 70),
        ("GARBAGE", "BROKEN_BIN", "Broken Bin", 80),
        ("GARBAGE", "SHIFTING_OF_BIN", "Shifting of Garbage Bin", 90),
        ("GARBAGE", "CLEANING_WATER_TABLE", "Cleaning of Water Table", 100),
        ("GARBAGE", "NUISANCE_GARBAGE_VEHICLE", "Nuisance by Garbage Tractor/Truck", 110),
        ("GARBAGE", "BURNING_OF_GARBAGE", "Burning of Garbage", 120),
        ("GARBAGE", "LORRY_WITHOUT_NET", "Garbage Lorry without Net", 130),
        ("GARBAGE", "SPILLING_FROM_LORRY", "Spilling of Garbage from Lorry", 140),
        ("GARBAGE", "BURNING_AT_DUMPING_GROUND", "Burning of Garbage at Dumping Ground", 150),
        # Air Quality
        ("AIR_QUALITY", "SMOKE_FROM_WASTE_BURNING", "Smoke from Waste Burning", 10),
        ("AIR_QUALITY", "DUST_POLLUTION", "Dust Pollution", 20),
        ("AIR_QUALITY", "INDUSTRIAL_EMISSION", "Industrial Smoke / Emission", 30),
        ("AIR_QUALITY", "FOUL_SMELL", "Foul Smell", 40),
        # Building Plan Permission
        ("BUILDING_PLAN", "UNAUTHORIZED_CONSTRUCTION", "Unauthorized Construction", 10),
        ("BUILDING_PLAN", "PLAN_DEVIATION", "Deviation from Approved Plan", 20),
        ("BUILDING_PLAN", "APPROVAL_QUERY", "Building Plan Approval Query", 30),
        # Flood
        ("FLOOD", "WATER_ENTERING_HOUSE", "Water Entering House", 10),
        ("FLOOD", "STREET_FLOODED", "Street Flooded", 20),
        ("FLOOD", "FALLEN_TREE", "Fallen Tree Blocking Road", 30),
        # General
        ("GENERAL_COMPLAINT", "OTHERS", "Others", 10),
        # Park and Playground
        ("PARK_PLAYGROUND", "PARK_MAINTENANCE", "Maintenance of Park", 10),
        ("PARK_PLAYGROUND", "DAMAGED_PLAY_EQUIPMENT", "Damaged Play Equipment", 20),
        ("PARK_PLAYGROUND", "TREE_TRIMMING", "Tree Trimming / Fallen Tree", 30),
        ("PARK_PLAYGROUND", "PARK_ENCROACHMENT", "Encroachment of Park", 40),
        # Public Health
        ("PUBLIC_HEALTH", "MOSQUITO_MENACE", "Mosquito Menace / Fogging Request", 10),
        ("PUBLIC_HEALTH", "DEAD_ANIMAL_REMOVAL", "Removal of Dead Animal", 20),
        ("PUBLIC_HEALTH", "STRAY_ANIMAL_NUISANCE", "Stray Dog / Cattle Nuisance", 30),
        ("PUBLIC_HEALTH", "UNHYGIENIC_EATERY", "Unhygienic Eatery / Food Safety", 40),
        # Public Toilet
        ("PUBLIC_TOILET", "TOILET_CLEANING", "Cleaning of Public Toilet", 10),
        ("PUBLIC_TOILET", "TOILET_REPAIR", "Repair of Public Toilet", 20),
        ("PUBLIC_TOILET", "TOILET_NO_WATER", "No Water Supply in Public Toilet", 30),
        ("PUBLIC_TOILET", "NEW_TOILET_REQUEST", "New Public Toilet Requirement", 40),
        # Road and Footpath
        ("ROAD_FOOTPATH", "POTHOLE_REPAIR", "Pothole Repair", 10),
        ("ROAD_FOOTPATH", "DAMAGED_ROAD", "Damaged Road", 20),
        ("ROAD_FOOTPATH", "DAMAGED_FOOTPATH", "Damaged Footpath", 30),
        ("ROAD_FOOTPATH", "FOOTPATH_ENCROACHMENT", "Encroachment of Footpath", 40),
        ("ROAD_FOOTPATH", "ROAD_RELAYING", "Relaying of Road", 50),
        # Storm Water Drains
        ("STORM_WATER_DRAIN", "BLOCKED_DRAIN", "Blocked / Overflowing Drain", 10),
        ("STORM_WATER_DRAIN", "DRAIN_DESILTING", "Desilting of Drain", 20),
        ("STORM_WATER_DRAIN", "DAMAGED_DRAIN", "Damaged Drain / Missing Slab", 30),
        ("STORM_WATER_DRAIN", "NEW_DRAIN_REQUEST", "New Drain Requirement", 40),
        # Street Light
        ("STREET_LIGHT", "LIGHT_NOT_WORKING", "Street Light Not Working", 10),
        ("STREET_LIGHT", "NEW_LIGHT_REQUEST", "New Street Light Provision", 20),
        ("STREET_LIGHT", "LIGHT_ON_DAYTIME", "Street Light Glowing in Daytime", 30),
        ("STREET_LIGHT", "DAMAGED_POLE", "Damaged / Leaning Light Pole", 40),
        # Tax and Licence
        ("TAX_LICENCE", "PROPERTY_TAX_QUERY", "Property Tax Query", 10),
        ("TAX_LICENCE", "PROFESSION_TAX_QUERY", "Profession Tax Query", 20),
        ("TAX_LICENCE", "TRADE_LICENCE_ISSUE", "Trade Licence Issue", 30),
        # Voter ID
        ("VOTER_ID", "NEW_VOTER_ID", "New Voter ID Request", 10),
        ("VOTER_ID", "VOTER_ID_CORRECTION", "Voter ID Correction", 20),
        # Water Stagnation
        ("WATER_STAGNATION", "RAIN_WATER_STAGNATION", "Rain Water Stagnation on Road", 10),
        ("WATER_STAGNATION", "SEWAGE_STAGNATION", "Sewage Water Stagnation", 20),
        ("WATER_STAGNATION", "VACANT_PLOT_STAGNATION", "Water Stagnation in Vacant Plot", 30),
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
