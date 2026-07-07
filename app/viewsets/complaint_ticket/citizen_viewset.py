"""Citizen-facing complaint ticket endpoints for the mobile app.

Registered under a NON-protected URL group (`/api/v1/citizen/complaint-tickets/`)
so the module-permission middleware skips it - access is gated by DRF
authentication (JWTUserAuthentication) and every query is hard-scoped to the
logged-in citizen, so a citizen can only ever see/raise their own tickets.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from rest_framework import viewsets, status as http_status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.subcategory_master import ComplaintSubcategory
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.status_master import ComplaintStatus
from app.models.complaint_ticket.source_master import ComplaintSource
from app.models.complaint_ticket.status_history import ComplaintStatusHistory
from app.models.complaint_ticket.ticket_attachment import ComplaintAttachment
from app.serializers.complaint_ticket.transaction_serializers import (
    ComplaintTicketSerializer,
    ComplaintTicketDetailSerializer,
)
from app.utils.complaint_ticket_routing import apply_routing_and_sla


def _as_customer(request):
    user = getattr(request, "user", None)
    return user if isinstance(user, CustomerCreation) else None


def _decimal_from_input(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.0000001"))
    except (InvalidOperation, ValueError):
        return None


class CitizenComplaintTicketViewSet(viewsets.ViewSet):
    """My-tickets API for citizens (mobile app)."""

    permission_classes = [IsAuthenticated]

    # ---- helpers ----
    def _scoped_qs(self, customer):
        return (
            ComplaintTicket.objects.filter(is_deleted=False)
            .select_related(
                "category", "subcategory", "priority", "status", "source",
                "assigned_team", "assigned_team__department", "assigned_staff",
            )
            .prefetch_related("status_history", "status_history__to_status", "attachments")
            .filter(Q(customer=customer) | Q(wa_phone=customer.contact_no))
            .order_by("-created")
        )

    # ---- GET /citizen/complaint-tickets/ ----
    def list(self, request):
        customer = _as_customer(request)
        if not customer:
            return Response([], status=http_status.HTTP_200_OK)
        data = ComplaintTicketSerializer(
            self._scoped_qs(customer), many=True, context={"request": request}
        ).data
        return Response(data)

    # ---- GET /citizen/complaint-tickets/{id}/ ----
    def retrieve(self, request, pk=None):
        customer = _as_customer(request)
        ticket = self._scoped_qs(customer).filter(unique_id=pk).first() if customer else None
        if not ticket:
            return Response({"detail": "Ticket not found."}, status=http_status.HTTP_404_NOT_FOUND)
        return Response(ComplaintTicketDetailSerializer(ticket, context={"request": request}).data)

    # ---- POST /citizen/complaint-tickets/ ----
    @transaction.atomic
    def create(self, request):
        customer = _as_customer(request)
        if not customer:
            return Response(
                {"detail": "Only a logged-in citizen can raise a complaint here."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        data = request.data
        category = ComplaintCategory.objects.filter(
            unique_id=data.get("category"), is_deleted=False
        ).first()
        if not category:
            return Response({"category": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)

        subcategory = ComplaintSubcategory.objects.filter(
            unique_id=data.get("subcategory"), is_deleted=False
        ).first()
        priority = (
            ComplaintPriority.objects.filter(unique_id=data.get("priority"), is_deleted=False).first()
            or category.default_priority
        )
        status_obj = (
            ComplaintStatus.objects.filter(status_code="SUBMITTED", is_deleted=False).first()
            or ComplaintStatus.objects.filter(status_code="DRAFT", is_deleted=False).first()
        )
        source = (
            ComplaintSource.objects.filter(source_code="MOBILE_APP", is_deleted=False).first()
            or ComplaintSource.objects.filter(source_code="WHATSAPP", is_deleted=False).first()
        )
        if not priority or not status_obj:
            return Response(
                {"detail": "Complaint ticket masters are not configured. Run the complaint-ticket seeder."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        description = str(data.get("description") or "").strip()
        ticket = ComplaintTicket.objects.create(
            customer=customer,
            category=category,
            subcategory=subcategory,
            priority=priority,
            status=status_obj,
            source=source,
            title=(description or category.category_name)[:120],
            description=description,
            location_text=str(data.get("location_text") or ""),
            wa_phone=customer.contact_no,
            profile_name=customer.customer_name,
            location_node=customer.location_node,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=status_obj,
            changed_by_customer=customer,
            changed_by_system=False,
            remarks="Raised via mobile app",
            visible_to_citizen=True,
        )
        # Derive routing (team + responsible staff) + SLA
        apply_routing_and_sla(ticket, save=True)

        return Response(
            ComplaintTicketDetailSerializer(ticket).data,
            status=http_status.HTTP_201_CREATED,
        )

    # ---- GET /citizen/complaint-tickets/meta/ ----
    @action(detail=False, methods=["get"])
    def meta(self, request):
        """Categories (+subcategories) + priorities so the chat can offer choices."""
        cats = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        subs = ComplaintSubcategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        pris = ComplaintPriority.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        return Response({
            "categories": [
                {
                    "unique_id": c.unique_id,
                    "category_code": c.category_code,
                    "category_name": c.category_name,
                    "default_priority": c.default_priority_id,
                    "default_priority_code": getattr(c.default_priority, "priority_code", None),
                    "requires_location": c.requires_location,
                }
                for c in cats
            ],
            "subcategories": [
                {
                    "unique_id": s.unique_id,
                    "category": s.category_id,
                    "subcategory_name": s.subcategory_name,
                }
                for s in subs
            ],
            "priorities": [
                {"unique_id": p.unique_id, "priority_code": p.priority_code, "priority_name": p.priority_name}
                for p in pris
            ],
        })


class PublicGrievanceViewSet(viewsets.ViewSet):
    """Public grievance intake API with no login or module permission requirement."""

    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @action(detail=False, methods=["get"])
    def meta(self, request):
        cats = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        return Response({
            "categories": [
                {
                    "unique_id": c.unique_id,
                    "category_code": c.category_code,
                    "category_name": c.category_name,
                    "requires_location": c.requires_location,
                    "requires_media": c.requires_media,
                }
                for c in cats
            ],
        })

    @transaction.atomic
    def create(self, request):
        data = request.data
        person_name = str(data.get("person_name") or data.get("profile_name") or "").strip()
        description = str(data.get("description") or "").strip()
        location_text = str(data.get("location_text") or "").strip()
        device_id = str(data.get("device_id") or "").strip()
        latitude = _decimal_from_input(data.get("latitude"))
        longitude = _decimal_from_input(data.get("longitude"))

        if not person_name:
            return Response({"person_name": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        if not description:
            return Response({"description": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        if latitude is None or longitude is None:
            return Response({"location": "Latitude and longitude are required."}, status=http_status.HTTP_400_BAD_REQUEST)

        category = ComplaintCategory.objects.filter(
            unique_id=data.get("category"), is_deleted=False, is_active=True
        ).first()
        if not category:
            category = ComplaintCategory.objects.filter(
                category_code="GENERAL", is_deleted=False, is_active=True
            ).first()
        if not category:
            category = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order").first()
        if not category:
            return Response(
                {"detail": "Complaint categories are not configured. Run the complaint-ticket seeder."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        priority = category.default_priority or ComplaintPriority.objects.filter(
            priority_code="P3", is_deleted=False
        ).first()
        status_obj = ComplaintStatus.objects.filter(status_code="SUBMITTED", is_deleted=False).first()
        if not priority or not status_obj:
            return Response(
                {"detail": "Complaint ticket masters are not configured. Run the complaint-ticket seeder."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        idempotency_key = f"publicgrivence:{device_id}" if device_id else None
        duplicate = None
        if idempotency_key:
            duplicate = ComplaintTicket.objects.filter(
                idempotency_key=idempotency_key,
                is_deleted=False,
            ).first()
        if not duplicate:
            duplicate = ComplaintTicket.objects.filter(
                latitude=latitude,
                longitude=longitude,
                is_deleted=False,
            ).first()
        if duplicate:
            return Response(
                {
                    "detail": "A public grievance was already submitted from this device or location.",
                    "ticket_no": duplicate.ticket_no,
                    "unique_id": duplicate.unique_id,
                },
                status=http_status.HTTP_409_CONFLICT,
            )

        source, _ = ComplaintSource.objects.get_or_create(
            source_code="PUBLIC_GRIEVANCE",
            defaults={"source_name": "Public Grievance", "is_active": True, "is_deleted": False},
        )
        ticket = ComplaintTicket.objects.create(
            source=source,
            category=category,
            priority=priority,
            status=status_obj,
            profile_name=person_name,
            title=(description or category.category_name)[:120],
            description=description,
            location_text=location_text,
            latitude=latitude,
            longitude=longitude,
            idempotency_key=idempotency_key,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=status_obj,
            changed_by_system=True,
            remarks="Raised via public grievance form",
            visible_to_citizen=True,
        )

        photo = request.FILES.get("photo") or request.FILES.get("file")
        if photo:
            ComplaintAttachment.objects.create(
                ticket=ticket,
                file=photo,
                file_name=getattr(photo, "name", None),
                file_type="photo",
                mime_type=getattr(photo, "content_type", None),
                file_size=getattr(photo, "size", None),
            )

        apply_routing_and_sla(ticket, save=True)

        return Response(
            {
                "message": "Public grievance submitted successfully.",
                "ticket_no": ticket.ticket_no,
                "unique_id": ticket.unique_id,
            },
            status=http_status.HTTP_201_CREATED,
        )
