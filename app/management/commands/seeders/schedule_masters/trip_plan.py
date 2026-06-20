from datetime import time

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class TripPlanSeeder(BaseSeeder):
    name = "TripPlanSeeder"

    # (panchayat_name, waste_type_name, scheduled_time, trigger_kg, max_kg)
    TRIP_PLANS = [
        ("Anthiyur Panchayat",         "Organic Waste",   time(7, 0),  200, 5000),
        ("Bhavani Panchayat",          "Plastic Waste",   time(7, 30), 150, 4000),
        ("Gobichettipalayam Panchayat","Paper Waste",     time(8, 0),  100, 1500),
        ("Kavundampalayam Panchayat",  "Metal Waste",     time(8, 30), 100, 4000),
        ("Modakkurichi Panchayat",     "Hazardous Waste", time(9, 0),   50, 1500),
    ]

    def run(self):
        district = District.objects.filter(name="Erode").first()
        if not district:
            self.log("District 'Erode' not found — run DistrictSeeder first.")
            return

        templates = list(StaffTemplate.objects.filter(
            is_deleted=False, status=StaffTemplate.Status.ACTIVE
        ).order_by("created_at")[:5])
        if not templates:
            self.log("No StaffTemplates found — run StaffTemplateSeeder first.")
            return

        vehicles = list(VehicleCreation.objects.filter(is_deleted=False).order_by("vehicle_no")[:5])
        if not vehicles:
            self.log("No vehicles found — run VehicleCreationSeeder first.")
            return

        supervisor = StaffcreationOfficeDetails.objects.filter(
            username="muthu.samy", is_deleted=False
        ).first()
        if not supervisor:
            supervisor = StaffcreationOfficeDetails.objects.filter(is_deleted=False).first()

        property_obj = Property.objects.filter(property_name="Residential", is_deleted=False).first()
        sub_property = SubProperty.objects.filter(
            property_id=property_obj, sub_property_name="Apartment", is_deleted=False
        ).first() if property_obj else None

        if not property_obj or not sub_property:
            self.log("Property/SubProperty not found — run PropertySeeder first.")
            return

        count = 0
        for idx, (panchayat_name, waste_type_name, sched_time, trigger_kg, max_kg) in enumerate(
            self.TRIP_PLANS
        ):
            panchayat = Panchayat.objects.filter(
                panchayat_name=panchayat_name, district_id=district
            ).first()
            waste_type = WasteType.objects.filter(
                waste_type_name=waste_type_name, is_deleted=False
            ).first()

            if not panchayat:
                self.log(f"Panchayat '{panchayat_name}' not found — skipping.")
                continue
            if not waste_type:
                self.log(f"WasteType '{waste_type_name}' not found — skipping.")
                continue

            template = templates[idx % len(templates)]
            vehicle = vehicles[idx % len(vehicles)]

            already_exists = TripPlan.objects.filter(
                district_id=district,
                panchayat_id=panchayat,
                staff_template_id=template,
                waste_type_id=waste_type,
                is_deleted=False,
            ).exists()
            if already_exists:
                self.log(f"TripPlan for '{panchayat_name}' already exists — skipping.")
                continue

            TripPlan.objects.create(
                district_id=district,
                panchayat_id=panchayat,
                staff_template_id=template,
                vehicle_id=vehicle,
                supervisor_id=supervisor,
                property_id=property_obj,
                sub_property_id=sub_property,
                waste_type_id=waste_type,
                scheduled_time=sched_time,
                trip_trigger_weight_kg=trigger_kg,
                max_vehicle_capacity_kg=max_kg,
                approval_status=TripPlan.ApprovalStatus.APPROVED,
                status=TripPlan.Status.ACTIVE,
                is_active=True,
                is_deleted=False,
            )
            count += 1
            self.log(f"Created TripPlan: {panchayat_name} - {waste_type_name}")

        self.log(f"---Trip plans seeded ({count} created)---")
