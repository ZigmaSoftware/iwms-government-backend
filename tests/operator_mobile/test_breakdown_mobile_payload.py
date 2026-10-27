"""Mobile GPS payloads must survive validation and storage at DB precision."""
from datetime import date, time
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import VehicleBreakdownSerializer
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.viewsets.core_modules.daily_operations.vehicle_breakdown_viewset import VehicleBreakdownViewSet


@pytest.mark.django_db
@pytest.mark.parametrize("format", ["json", "multipart"])
def test_mobile_gps_payload_is_saved_at_seven_decimal_places(format, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    vehicle = VehicleCreation.objects.create(vehicle_no="TN30CD1002")
    # No plan/stop graph is needed to exercise reporting an existing trip.
    DailyTripAssignment.objects.bulk_create([DailyTripAssignment(
        unique_id="TRIP-GPS", trip_plan_id="", staff_template_id="",
        vehicle_id=vehicle.pk, trip_date=date(2026, 10, 27), scheduled_time=time(9),
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
    )])
    payload = {
        "trip_assignment_id": "TRIP-GPS",
        "breakdown_vehicle_id": vehicle.pk,
        "breakdown_reason": "OTHER",
        "breakdown_time": "12:48:00",
        "breakdown_lat": 11.326428796243525,
        "breakdown_lng": 77.69683527417549,
        "collected_weight_before_breakdown_kg": "25",
        "breakdown_remarks": "test",
    }
    if format == "multipart":
        image = BytesIO()
        Image.new("RGB", (10, 10)).save(image, format="JPEG")
        payload["photos"] = SimpleUploadedFile("proof.jpg", image.getvalue(), "image/jpeg")
    raw = APIRequestFactory().post("/", payload, format=format)
    user = get_user_model().objects.create_user(username="breakdown-test")
    force_authenticate(raw, user=user)
    # Exercise the complete create/photo/audit/response path, independently
    # of the URL middleware's separately-tested role permissions.
    view = VehicleBreakdownViewSet.as_view({"post": "create"}, permission_classes=[])
    response = view(raw)
    assert response.status_code == 201, response.data
    report = VehicleBreakdown.objects.get(unique_id=response.data["unique_id"])
    assert report.breakdown_lat == Decimal("11.3264288")
    assert report.breakdown_lng == Decimal("77.6968353")
    assert report.approval_status == "PENDING"
    assert report.photos.count() == (1 if format == "multipart" else 0)
    if format == "multipart":
        assert report.photos.first().photo.storage.exists(report.photos.first().photo.name)


@pytest.mark.parametrize("field,value", [
    ("breakdown_lat", "91"), ("breakdown_lng", "181"),
    ("breakdown_lat", "NaN"), ("breakdown_lng", "Infinity"),
    ("breakdown_lat", "not a coordinate"), ("breakdown_lng", "1e999"),
])
def test_invalid_coordinates_are_still_rejected(field, value):
    with pytest.raises(ValidationError):
        VehicleBreakdownSerializer().fields[field].run_validation(value)


def test_optional_coordinates_remain_optional():
    serializer = VehicleBreakdownSerializer()
    assert serializer.fields["breakdown_lat"].run_validation(None) is None
    assert serializer.fields["breakdown_lng"].run_validation("") is None
