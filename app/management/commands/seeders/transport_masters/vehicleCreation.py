# core/management/commands/seeders/vehicles/vehicle_creation.py
from datetime import date

from app.management.commands.seeders.base import BaseSeeder
from app.models.transport_masters.fuel import Fuel
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class VehicleCreationSeeder(BaseSeeder):
    name = "vehicle_creation"

    def _get_or_create_vehicle_type(self, vehicle_type, company, project):
        obj, created = VehicleTypeCreation.objects.get_or_create(
            vehicleType=vehicle_type,
            defaults={
                "description": f"{vehicle_type} vehicle type",
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
            },
        )
        if not created and obj.is_deleted:
            obj.is_deleted = False
            obj.is_active = True
            obj.save(update_fields=["is_deleted", "is_active"])
        return obj

    def _get_or_create_fuel(self, fuel_type):
        obj, created = Fuel.objects.get_or_create(
            fuel_type=fuel_type,
            defaults={
                "description": f"{fuel_type} fuel type",
                "is_active": True,
                "is_deleted": False,
            },
        )
        if not created and obj.is_deleted:
            obj.is_deleted = False
            obj.is_active = True
            obj.save(update_fields=["is_deleted", "is_active"])
        return obj

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

        vt = {
            t: self._get_or_create_vehicle_type(t, company, project)
            for t in ["Compactor", "Tipping Truck", "Mini Truck", "Auto Rickshaw",
                      "Electric Vehicle", "Garbage Van", "Hook Lift Truck",
                      "Skip Loader", "Rear Loader"]
        }
        ft = {
            f: self._get_or_create_fuel(f)
            for f in ["Diesel", "CNG", "Petrol", "Electric"]
        }

        vehicles = [
            # (vehicle_no, vtype, fuel, capacity, mileage, service, insurance, expiry, condition, tank)
            ("TN09AB1234",     "Compactor",       "Diesel",   "10.00", "6.50",  "Quarterly maintenance",    "ICICI Lombard",  date(2026,12,31), VehicleCreation.ConditionChoices.NEW,         "150.00"),
            ("TN10CD5678",     "Tipping Truck",   "CNG",      "8.50",  "7.25",  "Bi-annual maintenance",    "Bajaj Allianz",  date(2026,10,15), VehicleCreation.ConditionChoices.SECOND_HAND, "120.00"),
            ("WET-VEHICLE-01", "Compactor",       "Diesel",   "1000.00","6.00", "Wet waste vehicle",        "ICICI Lombard",  date(2026,12,31), VehicleCreation.ConditionChoices.NEW,         "120.00"),
            ("DRY-VEHICLE-01", "Tipping Truck",   "Diesel",   "1000.00","6.20", "Dry waste vehicle",        "ICICI Lombard",  date(2026,12,31), VehicleCreation.ConditionChoices.NEW,         "120.00"),
            ("TN11EF9012",     "Mini Truck",      "Petrol",   "5.00",  "12.00", "Monthly check",            "New India",      date(2026,8,31),  VehicleCreation.ConditionChoices.NEW,         "60.00"),
            ("TN12GH3456",     "Auto Rickshaw",   "CNG",      "1.50",  "20.00", "Weekly inspection",        "Star Health",    date(2026,6,30),  VehicleCreation.ConditionChoices.NEW,         "30.00"),
            ("TN13IJ7890",     "Electric Vehicle","Electric", "4.00",  "0.00",  "Monthly battery check",    "HDFC Ergo",      date(2027,1,31),  VehicleCreation.ConditionChoices.NEW,         "0.00"),
            ("TN14KL2345",     "Garbage Van",     "Diesel",   "6.00",  "8.00",  "Quarterly service",        "Oriental Ins",   date(2026,9,30),  VehicleCreation.ConditionChoices.SECOND_HAND, "80.00"),
            ("TN15MN6789",     "Hook Lift Truck", "Diesel",   "12.00", "5.50",  "Semi-annual service",      "United India",   date(2026,11,30), VehicleCreation.ConditionChoices.NEW,         "180.00"),
            ("TN16OP1234",     "Skip Loader",     "Diesel",   "9.00",  "6.00",  "Quarterly maintenance",    "ICICI Lombard",  date(2026,12,31), VehicleCreation.ConditionChoices.NEW,         "140.00"),
            ("TN17QR5678",     "Rear Loader",     "CNG",      "7.00",  "7.00",  "Monthly service",          "Bajaj Allianz",  date(2026,10,31), VehicleCreation.ConditionChoices.NEW,         "110.00"),
            ("TN18ST9012",     "Compactor",       "Diesel",   "11.00", "6.20",  "Quarterly maintenance",    "New India",      date(2026,7,31),  VehicleCreation.ConditionChoices.SECOND_HAND, "160.00"),
            ("TN19UV3456",     "Tipping Truck",   "Diesel",   "9.50",  "6.80",  "Bi-annual maintenance",    "Star Health",    date(2026,9,30),  VehicleCreation.ConditionChoices.NEW,         "130.00"),
            ("TN20WX7890",     "Garbage Van",     "CNG",      "5.50",  "9.00",  "Monthly check",            "HDFC Ergo",      date(2027,3,31),  VehicleCreation.ConditionChoices.NEW,         "90.00"),
            ("TN21YZ2345",     "Mini Truck",      "Diesel",   "4.50",  "10.00", "Quarterly service",        "Oriental Ins",   date(2026,5,31),  VehicleCreation.ConditionChoices.SECOND_HAND, "70.00"),
        ]

        for (vno, vtype, fuel, cap, mil, svc, ins, expiry, cond, tank) in vehicles:
            obj, created = VehicleCreation.objects.get_or_create(
                vehicle_no=vno,
                defaults={
                    "vehicle_type": vt[vtype],
                    "fuel_type": ft[fuel],
                    "company_id": company,
                    "project_id": project,
                    "capacity": cap,
                    "mileage_per_liter": mil,
                    "service_record": svc,
                    "vehicle_insurance": ins,
                    "insurance_expiry_date": expiry,
                    "vehicle_condition": cond,
                    "fuel_tank_capacity": tank,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log(f"---Vehicle creation seeded ({len(vehicles)} records)---")
