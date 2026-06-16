from datetime import time

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


BASE_TIMES = [
    time(6, 0),  time(6, 30),  time(7, 0),  time(7, 30),  time(8, 0),
    time(8, 30),  time(9, 0),  time(9, 30),  time(10, 0), time(10, 30),
    time(11, 0), time(11, 30), time(12, 0),  time(12, 30), time(13, 0),
]


class TripPlanSeeder(BaseSeeder):
    name = "trip_plan"

    def run(self):
        company = Company.objects.filter(name="IWMS").first()
        project = (
            Project.objects.filter(name=f"{company.name} Main Project").first()
            if company else None
        )
        if not company or not project:
            self.log("TripPlanSeeder skipped (missing company/project).")
            return

        district = District.objects.filter(company_id=company, project_id=project).first()
        city = City.objects.filter(company_id=company, project_id=project).first()
        property_obj = Property.objects.filter(is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(is_deleted=False).first()
        supervisor = Staffcreation.objects.filter(is_deleted=False).order_by("created_at").first()

        if not all([district, city, property_obj, sub_property_obj, supervisor]):
            self.log("TripPlanSeeder skipped (missing dependencies).")
            return

        staff_templates = list(StaffTemplate.objects.filter(
            is_deleted=False, status="ACTIVE", approval_status="APPROVED"
        ).order_by("created_at"))

        vehicles = list(VehicleCreation.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).order_by("created_at"))

        if not staff_templates or not vehicles:
            self.log("TripPlanSeeder skipped (no staff templates or vehicles).")
            return

        waste_types = {
            "wet": WasteType.objects.filter(waste_type_name__iexact="Wet Waste", is_deleted=False).first(),
            "dry": WasteType.objects.filter(waste_type_name__iexact="Dry Waste", is_deleted=False).first(),
        }
        fallback_waste = WasteType.objects.filter(is_deleted=False).first()

        common_defaults = dict(
            district_id=district,
            city_id=city,
            supervisor_id=supervisor,
            property_id=property_obj,
            sub_property_id=sub_property_obj,
            trip_trigger_weight_kg=800,
            max_vehicle_capacity_kg=3000,
            approval_status=TripPlan.ApprovalStatus.APPROVED,
            status=TripPlan.Status.ACTIVE,
        )

        # Approve any already-active plans
        TripPlan.objects.filter(
            company_id=company, project_id=project, status=TripPlan.Status.ACTIVE,
        ).update(approval_status=TripPlan.ApprovalStatus.APPROVED)

        # ------------------------------------------------------------------
        # Ward-based trip plans
        # zone_id is derived from each ward's own zone FK (ward → Zone 1).
        # ------------------------------------------------------------------
        wards = list(Ward.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).select_related("zone_id").order_by("ward_name")[:15])

        ward_created = ward_skipped = 0
        for idx, ward in enumerate(wards):
            waste_key = "wet" if idx % 2 == 0 else "dry"
            waste_type = waste_types.get(waste_key) or fallback_waste
            if not waste_type:
                ward_skipped += 1
                continue

            staff_template = staff_templates[idx % len(staff_templates)]
            vehicle = vehicles[idx % len(vehicles)]

            _, created = TripPlan.objects.update_or_create(
                company_id=company,
                project_id=project,
                staff_template_id=staff_template,
                vehicle_id=vehicle,
                waste_type_id=waste_type,
                ward_id=ward,
                defaults={
                    **common_defaults,
                    "zone_id": ward.zone_id,   # zone comes from the ward's own zone
                    "panchayat_id": None,
                    "scheduled_time": BASE_TIMES[idx % len(BASE_TIMES)],
                },
            )
            if created:
                ward_created += 1

        # ------------------------------------------------------------------
        # Panchayat-based trip plans
        # Panchayats are rural; zone_id is not applicable (set to None).
        # ------------------------------------------------------------------
        panchayats = list(Panchayat.objects.filter(
            company_id=company, project_id=project, is_deleted=False
        ).order_by("panchayat_name")[:15])

        pan_created = pan_skipped = 0
        for idx, panchayat in enumerate(panchayats):
            waste_key = "wet" if idx % 2 == 0 else "dry"
            waste_type = waste_types.get(waste_key) or fallback_waste
            if not waste_type:
                pan_skipped += 1
                continue

            staff_template = staff_templates[idx % len(staff_templates)]
            vehicle = vehicles[idx % len(vehicles)]

            _, created = TripPlan.objects.update_or_create(
                company_id=company,
                project_id=project,
                staff_template_id=staff_template,
                vehicle_id=vehicle,
                waste_type_id=waste_type,
                panchayat_id=panchayat,
                defaults={
                    **common_defaults,
                    "zone_id": None,           # panchayats are rural, no zone
                    "ward_id": None,
                    "scheduled_time": BASE_TIMES[idx % len(BASE_TIMES)],
                },
            )
            if created:
                pan_created += 1

        self.log(
            f"---TripPlan seeded | ward plans created={ward_created}/{len(wards)} skipped={ward_skipped}"
            f" | panchayat plans created={pan_created}/{len(panchayats)} skipped={pan_skipped}---"
        )
