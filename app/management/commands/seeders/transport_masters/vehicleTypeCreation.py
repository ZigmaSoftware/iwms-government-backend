from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation


class VehicleTypeCreationSeeder(BaseSeeder):
    name = "vehicle_type_creation"

    # (vehicleType, description)
    VEHICLE_TYPES = [
        ("Compactor",         "Rear-loading compactor for municipal waste"),
        ("Tipping Truck",     "Hydraulic tipping truck for bulk waste"),
        ("Mini Truck",        "Small capacity mini truck for narrow lanes"),
        ("Auto Rickshaw",     "Three-wheeler for last-mile collection"),
        ("Electric Vehicle",  "Zero-emission battery electric collection vehicle"),
        ("Tractor",           "Tractor with trailer for agricultural waste"),
        ("Garbage Van",       "Closed-body van for sanitation use"),
        ("Hook Lift Truck",   "Hook-lift system for container transport"),
        ("Skip Loader",       "Skip bin loader truck"),
        ("Rear Loader",       "Rear-loading waste collection truck"),
        ("Side Loader",       "Side-loading automated collection truck"),
        ("Front Loader",      "Front-loading commercial waste truck"),
        ("Roll-On Roll-Off",  "RORO truck for large container bins"),
        ("Tanker",            "Liquid waste tanker vehicle"),
        ("Tricycle",          "Pedal/motor tricycle for small collections"),
    ]

    def run(self):
        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={
                "description": "Integrated Waste Management System",
                "is_active": True,
                "is_deleted": False,
            },
        )
        project, _ = Project.objects.get_or_create(
            name=f"{company.name} Main Project",
            company_id=company,
            defaults={
                "description": f"Default project for {company.name}",
                "is_active": True,
                "is_deleted": False,
            },
        )

        for vehicle_type, description in self.VEHICLE_TYPES:
            obj, created = VehicleTypeCreation.objects.get_or_create(
                vehicleType=vehicle_type,
                defaults={
                    "description": description,
                    "company_id": company,
                    "project_id": project,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created:
                update_fields = []
                if obj.is_deleted:
                    obj.is_deleted = False
                    update_fields.append("is_deleted")
                if not obj.is_active:
                    obj.is_active = True
                    update_fields.append("is_active")
                if update_fields:
                    obj.save(update_fields=update_fields)

        self.log(f"---Vehicle types seeded ({len(self.VEHICLE_TYPES)} records)---")
