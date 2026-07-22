"""Unit tests for the operator-mobile validation pipeline + auto-completion."""
from decimal import Decimal

import pytest
from django.utils import timezone

from app.models.masters.waste_masters.bins import Bins, BinType
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType
from app.models.masters.panchayat import Panchayat, GeoFencingType
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.masters.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.masters.transport_masters.trip_definition import TripDefinition
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.transport_masters.fuel import Fuel
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    build_scan_context,
    find_active_assignment_for_operator,
    progress_payload,
    resolve_bin_from_qr,
    validate_bin_against_assignment,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_staff(user_type, role_name, username, company, project, district, city, zone, ward):
    role, _ = StaffUserType.objects.get_or_create(
        name=role_name,
        usertype_id=user_type,
    )
    return Staffcreation.objects.create(
        employee_name=username,
        username=username,
        password="x",
        user_type_id=user_type,
        staffusertype_id=role,
        company_id=company,
        project_id=project,
        district_id=district,
        city_id=city,
        zone_id=zone,
        ward_id=ward,
        is_active=True,
        is_deleted=False,
    )


@pytest.fixture
def panchayat(db, state, district, city, company, project, area_type):
    rural, _ = AreaType.objects.get_or_create(
        name="Rural",
        state_id=state,
        district_id=district,
        city_id=city,
    )
    hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(
        area_type=rural,
        level_name="Panchayat",
    )
    return Panchayat.objects.create(
        panchayat_name="Test Panchayat",
        company_id=company,
        project_id=project,
        state_id=state,
        district_id=district,
        city_id=city,
        area_type_id=rural,
        hierarchy_id=hierarchy,
        geofencing_type=GeoFencingType.POLYGON,
        agreed_weight_kg=500,
        weight_unit="kg",
        latitude=Decimal("13.10"),
        longitude=Decimal("80.20"),
    )


@pytest.fixture
def other_panchayat(db, state, district, city, company, project):
    rural = AreaType.objects.get(name="Rural")
    hierarchy = AdministrativeHierarchy.objects.get(level_name="Panchayat")
    return Panchayat.objects.create(
        panchayat_name="Other Panchayat",
        company_id=company,
        project_id=project,
        state_id=state,
        district_id=district,
        city_id=city,
        area_type_id=rural,
        hierarchy_id=hierarchy,
        geofencing_type=GeoFencingType.POLYGON,
        agreed_weight_kg=500,
        weight_unit="kg",
        latitude=Decimal("13.20"),
        longitude=Decimal("80.30"),
    )


@pytest.fixture
def cp(db, panchayat, state, district, city, company, project):
    return Collection_point.objects.create(
        cp_name="CP-T-01",
        panchayat_id=panchayat,
        state_id=state,
        district_id=district,
        city_id=city,
        company_id=company,
        project_id=project,
        latitude=Decimal("13.10"),
        longitude=Decimal("80.20"),
    )


@pytest.fixture
def cp_in_other_panchayat(db, other_panchayat, state, district, city, company, project):
    return Collection_point.objects.create(
        cp_name="CP-OTH-01",
        panchayat_id=other_panchayat,
        state_id=state,
        district_id=district,
        city_id=city,
        company_id=company,
        project_id=project,
        latitude=Decimal("13.20"),
        longitude=Decimal("80.30"),
    )


@pytest.fixture
def waste_wet(db, company, project):
    return WasteType.objects.create(
        waste_type_name="Wet Waste", company_id=company, project_id=project
    )


@pytest.fixture
def waste_dry(db, company, project):
    return WasteType.objects.create(
        waste_type_name="Dry Waste", company_id=company, project_id=project
    )


@pytest.fixture
def bin_wet(db, cp, waste_wet, company, project):
    return Bins.objects.create(
        bin_name="CP Wet Bin",
        bin_qr="QR-T-CP01-WET",
        bin_capacity=240,
        bin_type=BinType.MEDIUM,
        bin_image="x.png",
        collection_point_id=cp,
        wastetype_id=waste_wet,
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def bin_dry(db, cp, waste_dry, company, project):
    return Bins.objects.create(
        bin_name="CP Dry Bin",
        bin_qr="QR-T-CP01-DRY",
        bin_capacity=240,
        bin_type=BinType.MEDIUM,
        bin_image="x.png",
        collection_point_id=cp,
        wastetype_id=waste_dry,
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def bin_wet_other(db, cp_in_other_panchayat, waste_wet, company, project):
    return Bins.objects.create(
        bin_name="Other CP Wet Bin",
        bin_qr="QR-T-OTH-WET",
        bin_capacity=240,
        bin_type=BinType.MEDIUM,
        bin_image="x.png",
        collection_point_id=cp_in_other_panchayat,
        wastetype_id=waste_wet,
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def operator(db, user_type, company, project, district, city, zone, ward):
    return _make_staff(
        user_type, "Company Operator", "operator_t",
        company, project, district, city, zone, ward,
    )


@pytest.fixture
def driver(db, user_type, company, project, district, city, zone, ward):
    return _make_staff(
        user_type, "Company Driver", "driver_t",
        company, project, district, city, zone, ward,
    )


@pytest.fixture
def staff_template(db, driver, operator, company, project):
    return StaffTemplate.objects.create(
        driver_id=driver,
        operator_id=operator,
        company_id=company,
        project_id=project,
        extra_operator_id=[],
        status="ACTIVE",
        approval_status="APPROVED",
    )


@pytest.fixture
def vehicle(db, company, project):
    fuel, _ = Fuel.objects.get_or_create(
        fuel_type="Diesel", defaults={"description": "Diesel"}
    )
    vtype, _ = VehicleTypeCreation.objects.get_or_create(
        vehicleType="Truck",
        defaults={"description": "Truck", "company_id": company, "project_id": project},
    )
    return VehicleCreation.objects.create(
        vehicle_no="V-T-01",
        vehicle_type=vtype,
        fuel_type=fuel,
        company_id=company,
        project_id=project,
        capacity=Decimal("1000.00"),
        mileage_per_liter=Decimal("6.00"),
        vehicle_insurance="X",
        insurance_expiry_date=timezone.localdate(),
        vehicle_condition=VehicleCreation.ConditionChoices.NEW,
        fuel_tank_capacity=Decimal("120.00"),
    )



@pytest.fixture
def assignment_wet(
    db, trip_definition, staff_template, panchayat, waste_wet, vehicle, company, project
):
    return DailyTripAssignment.objects.create(
        company_id=company,
        project_id=project,
        trip_definition_id=trip_definition,
        staff_template_id=staff_template,
        panchayat_id=panchayat,
        collection_point_id=None,
        waste_type_id=waste_wet,
        vehicle_id=vehicle,
        trip_date=timezone.localdate(),
        scheduled_time=timezone.localtime().time(),
        status=DailyTripAssignment.STATUS_SCHEDULED,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
    )


@pytest.fixture
def trip_cp(db, assignment_wet, cp, bin_wet):
    return DailyTripCollectionPoint.objects.create(
        trip_assignment_id=assignment_wet,
        collection_point_id=cp,
        bin_id=bin_wet,
        sequence=1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOperatorFlowValidation:
    def test_no_active_trip_raises(self, operator):
        with pytest.raises(OperatorFlowError) as exc:
            find_active_assignment_for_operator(operator)
        assert exc.value.code == "NO_ACTIVE_TRIP"

    def test_active_trip_found(self, operator, assignment_wet, trip_cp):
        result = find_active_assignment_for_operator(operator)
        assert result.unique_id == assignment_wet.unique_id

    def test_bin_not_found(self, operator, assignment_wet, trip_cp):
        with pytest.raises(OperatorFlowError) as exc:
            resolve_bin_from_qr("QR-UNKNOWN")
        assert exc.value.code == "BIN_NOT_FOUND"

    def test_wrong_waste_type(self, operator, assignment_wet, trip_cp, bin_dry):
        with pytest.raises(OperatorFlowError) as exc:
            validate_bin_against_assignment(bin_dry, assignment_wet)
        assert exc.value.code == "WRONG_WASTE_TYPE"

    def test_wrong_panchayat(self, operator, assignment_wet, trip_cp, bin_wet_other):
        with pytest.raises(OperatorFlowError) as exc:
            validate_bin_against_assignment(bin_wet_other, assignment_wet)
        assert exc.value.code == "WRONG_PANCHAYAT"

    def test_cp_not_in_trip(self, operator, assignment_wet, bin_wet):
        # No DailyTripCollectionPoint exists yet for assignment_wet ↔ cp
        with pytest.raises(OperatorFlowError) as exc:
            validate_bin_against_assignment(bin_wet, assignment_wet)
        assert exc.value.code == "CP_NOT_IN_TRIP"

    def test_already_collected(self, operator, assignment_wet, trip_cp, bin_wet):
        trip_cp.mark_collected(weight_kg=Decimal("10"), collected_by=operator)
        with pytest.raises(OperatorFlowError) as exc:
            validate_bin_against_assignment(bin_wet, assignment_wet)
        assert exc.value.code == "ALREADY_COLLECTED"

    def test_build_scan_context_happy_path(
        self, operator, assignment_wet, trip_cp, bin_wet
    ):
        ctx = build_scan_context(bin_wet.bin_qr, operator)
        assert ctx.bin.unique_id == bin_wet.unique_id
        assert ctx.assignment.unique_id == assignment_wet.unique_id
        assert ctx.trip_cp.unique_id == trip_cp.unique_id


@pytest.mark.django_db
class TestTripAutoCompletion:
    def test_progress_payload_initial(self, assignment_wet, trip_cp):
        progress = progress_payload(assignment_wet)
        assert progress == {"collected": 0, "total": 1, "completed": False}

    def test_completes_when_all_cps_collected(
        self, operator, assignment_wet, trip_cp
    ):
        trip_cp.mark_collected(weight_kg=Decimal("10"), collected_by=operator)
        assignment_wet.refresh_from_db()
        assert assignment_wet.status == DailyTripAssignment.STATUS_COMPLETED
        progress = progress_payload(assignment_wet)
        assert progress == {"collected": 1, "total": 1, "completed": True}
