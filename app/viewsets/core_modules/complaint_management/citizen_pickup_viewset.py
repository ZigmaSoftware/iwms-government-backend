"""Citizen "today's pickup" status and the "I'm home now" action.

    GET  /citizen/my-pickup-today/          today's household stop for me
    POST /citizen/my-pickup-today/im-home/  {note?} — tell the crew I'm home

Registered under the `citizen/` URL group, which is not a protected module in
ModulePermissionMiddleware (auth-only, like citizen/complaint-tickets); every
lookup is scoped to the logged-in customer. Logic lives in
app/services/customer_availability.py.
"""

from django.utils import timezone
from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.services.customer_availability import (
    AvailabilityError,
    mark_customer_available,
    missed_pickup_ticket,
    todays_stop,
)
from app.services.daily_service_notice import notice_for_customer, serialize_notice
from app.utils.audit_mixin import log_common_audit, serialize_instance_for_audit
from app.utils.waste_images import build_media_url, capture_images_for_customer
from app.viewsets.core_modules.complaint_management.citizen_viewset import _as_customer


def _waste_breakdown(collection):
    if collection is None:
        return []
    buckets = (
        ("Wet Waste", collection.wet_waste),
        ("Dry Waste", collection.dry_waste),
        ("Mixed Waste", collection.mixed_waste),
        ("Sanitary Waste", collection.sanitary_waste),
    )
    return [
        {"waste_type": label, "weight_kg": float(weight)}
        for label, weight in buckets
        if float(weight or 0) > 0
    ]


def _evidence_url(image_field, request=None):
    if not image_field:
        return None
    try:
        url = image_field.url
    except (AttributeError, ValueError):
        return None
    return request.build_absolute_uri(url) if request is not None else url


def _payload(stop, request=None, customer=None):
    notice = notice_for_customer(customer, timezone.localdate()) if customer else None
    if stop is None:
        return {"stop": None, "service_notice": serialize_notice(notice)}
    ticket = missed_pickup_ticket(stop)
    collection = stop.waste_collection
    media_request = request if hasattr(request, "build_absolute_uri") else None
    # This codebase's WasteCollection has no image column; keep the lookup
    # for parity and fall back to the capture-flow photos.
    image_url = build_media_url(getattr(collection, "image", None), media_request)
    if not image_url and stop.is_collected:
        captures = capture_images_for_customer(
            stop.customer_id,
            collection_date=timezone.localdate(),
            request=media_request,
        )
        image_url = captures[0]["url"] if captures else None
    return {
        "service_notice": serialize_notice(notice),
        "stop": {
            "unique_id": stop.unique_id,
            "trip_assignment_id": stop.trip_assignment_id,
            "trip_date": timezone.localdate().isoformat(),
            "status": stop.status,
            "status_reason": stop.status_reason,
            "status_updated_at": stop.updated_at,
            "is_collected": stop.is_collected,
            "collected_at": stop.collected_at,
            "collected_weight_kg": stop.collected_weight_kg,
            "collection_image_url": image_url,
            "status_evidence_image_url": _evidence_url(
                stop.status_evidence_image, media_request
            ),
            "waste_breakdown": _waste_breakdown(collection),
            "customer_available_at": stop.customer_available_at,
            "customer_available_note": stop.customer_available_note,
            "missed_pickup_ticket_no": getattr(ticket, "ticket_no", None),
        },
    }


class CitizenPickupViewSet(viewsets.ViewSet):
    throttle_scope = "citizen_pickup"
    permission_classes = [IsAuthenticated]

    def list(self, request):
        customer = _as_customer(request)
        if not customer:
            return Response({"stop": None, "service_notice": None})
        return Response(_payload(todays_stop(customer), request, customer))

    @action(detail=False, methods=["post"], url_path="im-home")
    def im_home(self, request):
        customer = _as_customer(request)
        if not customer:
            return Response(
                {"detail": "Only a logged-in citizen can do this."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        previous = todays_stop(customer)
        previous_data = serialize_instance_for_audit(previous) if previous else None
        try:
            stop, created = mark_customer_available(
                customer, note=request.data.get("note")
            )
        except AvailabilityError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        if created:
            log_common_audit(
                request,
                module_name="citizen",
                endpoint_name="my-pickup-today",
                instance=stop,
                previous_data=previous_data,
                new_data=serialize_instance_for_audit(stop),
            )
        body = _payload(stop, request, customer)
        body["notified"] = created
        return Response(body)
