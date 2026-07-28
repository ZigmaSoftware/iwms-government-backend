from django.db import transaction
from django.utils import timezone

from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.utils.audit_mixin import AuditViewSetMixin

from app.models.core_modules.complaint_management.address_change_request import ComplaintAddressChangeRequest
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.status_history import ComplaintStatusHistory
from app.models.core_modules.schedule_setup.trip_plan import TripPlan

from app.serializers.core_modules.complaint_management.transaction_serializers import (
    ComplaintAddressChangeRequestSerializer,
)

# (customer field, request "new_*" field) pairs for the flat geo overwrite.
GEO_FIELD_MAP = (
    ("state", "new_state"),
    ("district", "new_district"),
    ("area_type", "new_area_type"),
    ("corporation", "new_corporation"),
    ("municipality", "new_municipality"),
    ("town_panchayat", "new_town_panchayat"),
    ("panchayat_union", "new_panchayat_union"),
    ("panchayat", "new_panchayat"),
)


def _resolve_status(status_code):
    return ComplaintStatus.objects.filter(status_code=status_code, is_deleted=False).first()


def _snapshot_customer_address(customer):
    return {
        "building_no": customer.building_no,
        "street": customer.street,
        "area": customer.area,
        "pincode": customer.pincode,
        "latitude": customer.latitude,
        "longitude": customer.longitude,
        "state_id": customer.state_id,
        "district_id": customer.district_id,
        "area_type_id": customer.area_type_id,
        "corporation_id": customer.corporation_id,
        "municipality_id": customer.municipality_id,
        "town_panchayat_id": customer.town_panchayat_id,
        "panchayat_union_id": customer.panchayat_union_id,
        "panchayat_id": customer.panchayat_id,
    }


class ComplaintAddressChangeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintAddressChangeRequestSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "address-change"

    def get_queryset(self):
        qs = ComplaintAddressChangeRequest.objects.filter(is_deleted=False).select_related(
            "ticket", "customer"
        ).order_by("-created")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        return qs

    def perform_create(self, serializer):
        # Snapshot the current customer address at request time
        instance = serializer.save()
        if instance.customer and not instance.old_address_snapshot:
            instance.old_address_snapshot = _snapshot_customer_address(instance.customer)
            instance.save(update_fields=["old_address_snapshot"])
        # audit
        new_data = self._serialize_instance(instance)
        self.log_audit(self.request, instance=instance, previous_data=None, new_data=new_data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "Request deleted successfully"}, status=http_status.HTTP_200_OK)

    # ----------------------------------------------------------
    # POST /address-change/{id}/verify/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, unique_id=None):
        req = self.get_object()
        req.verification_status = ComplaintAddressChangeRequest.VerificationStatus.VERIFIED
        req.verified_by = request.user if request.user.is_authenticated else None
        req.verified_at = timezone.now()
        req.verification_remarks = request.data.get("verification_remarks")
        req.save(update_fields=["verification_status", "verified_by", "verified_at", "verification_remarks"])
        return Response(self.get_serializer(req).data)

    # ----------------------------------------------------------
    # POST /address-change/{id}/approve/  -> overwrite CustomerCreation
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="approve")
    @transaction.atomic
    def approve(self, request, unique_id=None):
        req = self.get_object()
        customer = req.customer
        if not customer:
            return Response({"detail": "No customer linked to this request."}, status=http_status.HTTP_400_BAD_REQUEST)

        # Keep snapshot of the address being replaced
        if not req.old_address_snapshot:
            req.old_address_snapshot = _snapshot_customer_address(customer)

        # Overwrite in place (no history table per project decision)
        if req.new_building_no is not None:
            customer.building_no = req.new_building_no
        if req.new_street is not None:
            customer.street = req.new_street
        if req.new_area is not None:
            customer.area = req.new_area
        if req.new_pincode is not None:
            customer.pincode = req.new_pincode
        if req.new_latitude is not None:
            customer.latitude = req.new_latitude
        if req.new_longitude is not None:
            customer.longitude = req.new_longitude
        new_geo_fields = {
            customer_field: getattr(req, f"{request_field}_id", None)
            for customer_field, request_field in GEO_FIELD_MAP
        }
        if any(new_geo_fields.values()):
            # Clear any previously-set local body before applying the new one,
            # since only one of corporation/municipality/.../panchayat should
            # be populated at a time.
            for customer_field, _ in GEO_FIELD_MAP:
                setattr(customer, customer_field, None)
            for customer_field, value in new_geo_fields.items():
                if value:
                    setattr(customer, f"{customer_field}_id", value)
        customer.save()

        req.approved_by = request.user if request.user.is_authenticated else None
        req.approved_at = timezone.now()
        req.save()

        # Move ticket to RESOLVED
        ticket = req.ticket
        resolved = _resolve_status("RESOLVED")
        route_warning = None
        if resolved:
            old_status = ticket.status
            ticket.status = resolved
            ticket.resolved_at = timezone.now()
            ticket.save(update_fields=["status", "resolved_at"])
            ComplaintStatusHistory.objects.create(
                ticket=ticket,
                from_status=old_status,
                to_status=resolved,
                changed_by_user=request.user if request.user.is_authenticated else None,
                remarks="Address change approved",
            )

        # Flag route reassignment if the new location isn't covered by any active trip plan
        if any(new_geo_fields.values()):
            # Most specific populated level wins - a district-only match still
            # counts as "covered" if no local-body-level plan exists.
            covered = False
            for field in ("panchayat", "panchayat_union", "town_panchayat", "municipality", "corporation", "district", "state"):
                value = new_geo_fields.get(field)
                if value and TripPlan.objects.filter(**{f"{field}_id": value}, is_deleted=False).exists():
                    covered = True
                    break
            if not covered:
                most_specific = None
                for customer_field, _ in reversed(GEO_FIELD_MAP):
                    if new_geo_fields.get(customer_field):
                        most_specific = new_geo_fields[customer_field]
                        break
                route_warning = (
                    f"New location {most_specific} is not covered by any active TripPlan - "
                    "manual route reassignment required."
                )

        data = self.get_serializer(req).data
        if route_warning:
            data["route_warning"] = route_warning
        return Response(data)

    # ----------------------------------------------------------
    # POST /address-change/{id}/reject/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="reject")
    @transaction.atomic
    def reject(self, request, unique_id=None):
        req = self.get_object()
        req.verification_status = ComplaintAddressChangeRequest.VerificationStatus.REJECTED
        req.rejection_reason = request.data.get("rejection_reason")
        req.save(update_fields=["verification_status", "rejection_reason"])

        ticket = req.ticket
        rejected = _resolve_status("REJECTED")
        if rejected:
            old_status = ticket.status
            ticket.status = rejected
            ticket.save(update_fields=["status"])
            ComplaintStatusHistory.objects.create(
                ticket=ticket,
                from_status=old_status,
                to_status=rejected,
                changed_by_user=request.user if request.user.is_authenticated else None,
                remarks=f"Address change rejected: {req.rejection_reason or ''}",
            )
        return Response(self.get_serializer(req).data)
