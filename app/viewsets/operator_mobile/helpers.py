import json
from dataclasses import dataclass
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from app.models.assets.bins import Bins
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.user_creations.staffcreation import Staffcreation


class OperatorFlowError(Exception):
    """Raised when an operator scan/validate fails business rules."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


@dataclass
class ScanContext:
    bin: Bins
    assignment: DailyTripAssignment
    trip_cp: DailyTripCollectionPoint


def resolve_operator_staff(user) -> Staffcreation:
    if not isinstance(user, Staffcreation):
        raise OperatorFlowError(
            "NOT_AN_OPERATOR_ACCOUNT",
            "Authenticated account is not a staff record.",
            http_status=403,
        )
    return user


def find_active_assignment_for_operator(staff: Staffcreation) -> DailyTripAssignment:
    today = timezone.localdate()

    base = (
        DailyTripAssignment.objects
        .filter(trip_date=today, is_deleted=False)
        .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
        .select_related(
            "panchayat",
            "vehicle_id",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__operator_id",
        )
        .prefetch_related("waste_types")
        .order_by("unique_id")
    )

    # Driver+operator app merge: the same mobile endpoints serve both roles, so
    # resolve today's assignment where the staff is either the template's operator
    # OR its driver.
    assignment = base.filter(
        Q(staff_template_id__operator_id=staff)
        | Q(staff_template_id__driver_id=staff)
    ).first()
    if assignment is None:
        # Extra-operator fallback: walk staff_templates and check JSON membership in Python
        # (avoids SQLite-incompatible JSON __contains lookups).
        for candidate in base:
            extras = getattr(candidate.staff_template_id, "extra_operator_id", None) or []
            if staff.staff_unique_id in extras:
                assignment = candidate
                break

    if not assignment:
        raise OperatorFlowError(
            "NO_ACTIVE_TRIP",
            "No trip is assigned to you for today.",
        )
    return assignment


def find_all_active_assignments_for_operator(staff: Staffcreation):
    """Every non-cancelled trip assigned to the operator/driver today, ordered by
    unique_id. A driver can hold more than one (e.g. a bin trip AND a household
    trip) — the mobile header carousel lists them all. Never raises: returns an
    empty list when there is no trip today."""
    today = timezone.localdate()

    base = (
        DailyTripAssignment.objects
        .filter(trip_date=today, is_deleted=False)
        .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
        .select_related(
            "panchayat",
            "vehicle_id",
            "trip_plan_id",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__operator_id",
        )
        .prefetch_related("waste_types")
        .order_by("unique_id")
    )

    assignments = list(
        base.filter(
            Q(staff_template_id__operator_id=staff)
            | Q(staff_template_id__driver_id=staff)
        )
    )
    if not assignments:
        for candidate in base:
            extras = getattr(candidate.staff_template_id, "extra_operator_id", None) or []
            if staff.staff_unique_id in extras:
                assignments.append(candidate)
    return assignments


def _extract_bin_identifier(raw: str) -> str:
    """The printed bin QR encodes JSON like {"id": "BIN-..."} (see
    app/utils/bin_qr.py). Card taps in the app instead send the stored bin_qr
    image path. Pull the bin unique_id out of whatever form we receive."""
    raw = (raw or "").strip()
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            return str(data.get("id") or data.get("unique_id") or "").strip()
        except (ValueError, TypeError):
            return raw
    if "/media/bin_qr/" in raw:
        filename = raw.rsplit("/", 1)[-1]
        return filename.rsplit(".", 1)[0]
    if raw.startswith("bin_qr/"):
        filename = raw.rsplit("/", 1)[-1]
        return filename.rsplit(".", 1)[0]
    return raw


def resolve_bin_from_qr(bin_qr: str) -> Bins:
    identifier = _extract_bin_identifier(bin_qr)
    bin_obj = (
        Bins.objects
        .filter(is_deleted=False)
        # Match the decoded unique_id (camera scan / raw id) OR the stored
        # bin_qr image path (app card-tap sends the path from my-trip-today).
        .filter(Q(unique_id=identifier) | Q(bin_qr=bin_qr))
        .select_related(
            "collection_point_id",
            "collection_point_id__state",
            "collection_point_id__district",
            "collection_point_id__area_type",
            "collection_point_id__corporation",
            "collection_point_id__municipality",
            "collection_point_id__town_panchayat",
            "collection_point_id__panchayat_union",
            "collection_point_id__panchayat",
            "wastetype_id",
        )
        .first()
    )
    if not bin_obj:
        raise OperatorFlowError(
            "BIN_NOT_FOUND",
            f"No bin found for QR '{bin_qr}'.",
            http_status=404,
        )
    return bin_obj


def validate_bin_against_assignment(
    bin_obj: Bins, assignment: DailyTripAssignment
) -> DailyTripCollectionPoint:
    trip_waste_type_ids = {wt.unique_id for wt in assignment.waste_types.all()}
    if str(bin_obj.wastetype_id_id) not in trip_waste_type_ids:
        bin_waste = getattr(bin_obj.wastetype_id, "waste_type_name", "unknown")
        trip_waste = ", ".join(wt.waste_type_name for wt in assignment.waste_types.all()) or "unknown"
        raise OperatorFlowError(
            "WRONG_WASTE_TYPE",
            f"This bin is {bin_waste}; your trip collects {trip_waste}.",
        )

    cp = bin_obj.collection_point_id
    cp_panchayat_id = getattr(cp, "panchayat_id", None)
    if not cp_panchayat_id or str(cp_panchayat_id) != str(assignment.panchayat_id):
        raise OperatorFlowError(
            "WRONG_PANCHAYAT",
            "This bin is outside your assigned panchayat.",
        )

    trip_cp = (
        DailyTripCollectionPoint.objects
        .filter(
            trip_assignment_id=assignment,
            collection_point_id=cp,
            bin_id=bin_obj,
            is_deleted=False,
        )
        .select_related("collection_point_id", "bin_id")
        .first()
    )
    if not trip_cp:
        raise OperatorFlowError(
            "CP_NOT_IN_TRIP",
            "This bin is not part of your assigned collection points.",
        )

    if trip_cp.is_collected:
        raise OperatorFlowError(
            "ALREADY_COLLECTED",
            "This collection point has already been marked collected.",
            http_status=409,
        )
    if trip_cp.status == DailyTripCollectionPoint.STATUS_MISSED:
        raise OperatorFlowError(
            "ALREADY_MISSED",
            "This collection point is already marked not available.",
            http_status=409,
        )

    return trip_cp


def build_scan_context(bin_qr: str, operator: Staffcreation) -> ScanContext:
    assignment = find_active_assignment_for_operator(operator)
    bin_obj = resolve_bin_from_qr(bin_qr)
    trip_cp = validate_bin_against_assignment(bin_obj, assignment)
    return ScanContext(bin=bin_obj, assignment=assignment, trip_cp=trip_cp)


def progress_payload(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(
        1 for c in children
        if c.status == DailyTripCollectionPoint.STATUS_COLLECTED
    )
    resolved = sum(
        1 for c in children
        if c.status in {
            DailyTripCollectionPoint.STATUS_COLLECTED,
            DailyTripCollectionPoint.STATUS_MISSED,
        }
    )
    return {
        "collected": collected,
        "total": total,
        "resolved": resolved,
        "completed": total > 0 and resolved == total,
    }


def _bin_qr_image_url(bin_obj: Bins, request=None) -> str | None:
    qr = getattr(bin_obj, "bin_qr", None)
    try:
        url = qr.url if qr else None
    except (ValueError, AttributeError):
        url = None
    if not url:
        return None
    return request.build_absolute_uri(url) if request is not None else url


def serialize_bin_brief(bin_obj: Bins, request=None) -> dict:
    return {
        "unique_id": bin_obj.unique_id,
        "bin_name": bin_obj.bin_name,
        # The app sends this value back to validate/scan. Keep it as the stable
        # bin identifier; the PNG URL is exposed separately for display.
        "bin_qr": bin_obj.unique_id,
        "bin_qr_image_url": _bin_qr_image_url(bin_obj, request=request),
        "bin_capacity": bin_obj.bin_capacity,
        "waste_type": {
            "unique_id": bin_obj.wastetype_id_id,
            "name": getattr(bin_obj.wastetype_id, "waste_type_name", None),
        },
    }


def serialize_cp_brief(cp) -> dict:
    return {
        "unique_id": cp.unique_id,
        "name": cp.cp_name,
        "latitude": str(cp.latitude) if cp.latitude is not None else None,
        "longitude": str(cp.longitude) if cp.longitude is not None else None,
    }


def serialize_trip_cp_brief(trip_cp: DailyTripCollectionPoint) -> dict:
    return {
        "unique_id": trip_cp.unique_id,
        "sequence": trip_cp.sequence,
        "is_collected": trip_cp.is_collected,
        "status": trip_cp.status,
        "status_reason": trip_cp.status_reason,
        "collected_at": trip_cp.collected_at.isoformat() if trip_cp.collected_at else None,
        "collected_weight_kg": (
            str(trip_cp.collected_weight_kg)
            if trip_cp.collected_weight_kg is not None
            else None
        ),
    }


def serialize_assignment_brief(assignment: DailyTripAssignment) -> dict:
    panchayat = assignment.panchayat
    vehicle = assignment.vehicle_id
    return {
        "unique_id": assignment.unique_id,
        "status": assignment.status,
        "trip_date": assignment.trip_date.isoformat(),
        "panchayat": {
            "unique_id": panchayat.unique_id,
            "name": panchayat.panchayat_name,
        },
        "waste_types": [
            {"unique_id": wt.unique_id, "name": wt.waste_type_name}
            for wt in assignment.waste_types.all()
        ],
        "vehicle": (
            {
                "unique_id": vehicle.unique_id,
                "vehicle_no": vehicle.vehicle_no,
                "capacity": str(vehicle.capacity),
            }
            if vehicle
            else None
        ),
    }


def maybe_resolve_driver(assignment: DailyTripAssignment) -> Optional[Staffcreation]:
    template = assignment.staff_template_id
    return getattr(template, "driver_id", None)
