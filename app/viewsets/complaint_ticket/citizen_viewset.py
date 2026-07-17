"""Citizen-facing complaint ticket endpoints for the mobile app.

Registered under a NON-protected URL group (`/api/v1/citizen/complaint-tickets/`)
so the module-permission middleware skips it - access is gated by DRF
authentication (JWTUserAuthentication) and every query is hard-scoped to the
logged-in citizen, so a citizen can only ever see/raise their own tickets.
"""

from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

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
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.assets.wastetype import WasteType
from app.serializers.complaint_ticket.transaction_serializers import (
    ComplaintTicketSerializer,
    ComplaintTicketDetailSerializer,
)
from app.utils.complaint_ticket_routing import apply_routing_and_sla, _add_business_minutes
from app.utils.email_utils import send_grievance_confirmation_email

# Public grievance duplicate-submission cooldown: after this window has
# passed, the same device may submit another grievance. Location is not used
# for dedup since multiple citizens can legitimately report the same spot.
PUBLIC_GRIEVANCE_DUPLICATE_WINDOW = timedelta(hours=6)

# Flat local-body masters one level below District - the "city" choice on the
# public form (mirrors geoApi.localBodies on the frontend). Each entry is
# (ticket field name, model, display-name attribute).
LOCAL_BODY_SOURCES = (
    ("corporation", Corporation, "corporation_name"),
    ("municipality", Municipality, "municipality_name"),
    ("town_panchayat", TownPanchayat, "town_panchayat_name"),
    ("panchayat_union", PanchayatUnion, "union_name"),
    ("panchayat", Panchayat, "panchayat_name"),
)

# Flat geo FK field names copied from a customer onto their ticket.
CUSTOMER_GEO_FIELDS = (
    "state", "district", "corporation", "municipality",
    "town_panchayat", "panchayat_union", "panchayat",
)


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


def _multi_values(data, key):
    """Read all values for `key` from a multi-valued request body (multipart
    form-data repeats the key; a JSON body may send an actual list)."""
    getlist = getattr(data, "getlist", None)
    if callable(getlist):
        values = [str(v).strip() for v in getlist(key) if str(v).strip()]
        if values:
            return values
    value = data.get(key)
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if value else []


def _sla_strictness_key(waste_type):
    """Sort key so the most time-sensitive waste type (smallest due window)
    wins when several are selected on one ticket."""
    if waste_type.resolve_within_minutes is not None:
        return waste_type.resolve_within_minutes
    if waste_type.assign_within_minutes is not None:
        return waste_type.assign_within_minutes
    return float("inf")


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
        # The ticket inherits the citizen's own flat geo (state/district/
        # local body) straight from their customer record.
        customer_geo = {
            f"{field}_id": getattr(customer, f"{field}_id", None)
            for field in CUSTOMER_GEO_FIELDS
        }
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
            **customer_geo,
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
        waste_types = WasteType.objects.filter(is_deleted=False, is_active=True).order_by("waste_type_name")
        categories = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order")
        subcategories = ComplaintSubcategory.objects.filter(
            is_deleted=False, is_active=True, category__is_deleted=False, category__is_active=True
        ).order_by("sort_order")
        return Response({
            "waste_types": [
                {"unique_id": w.unique_id, "waste_type_name": w.waste_type_name}
                for w in waste_types
            ],
            "categories": [
                {"unique_id": c.unique_id, "category_name": c.category_name}
                for c in categories
            ],
            "subcategories": [
                {"unique_id": s.unique_id, "category": s.category_id, "subcategory_name": s.subcategory_name}
                for s in subcategories
            ],
        })

    # ---- GET /publicgrievance/states/ ----
    # Read-only, name-only passthroughs onto the flat geo masters so the
    # public form can offer a state/district/city picker without needing a
    # login (the real /common-masters/ and /masters/ APIs are behind auth).
    @action(detail=False, methods=["get"])
    def states(self, request):
        rows = State.objects.filter(is_deleted=False, is_active=True).order_by("name")
        return Response([{"unique_id": s.unique_id, "name": s.name} for s in rows])

    # ---- GET /publicgrievance/districts/?state=<state id> ----
    @action(detail=False, methods=["get"])
    def districts(self, request):
        rows = District.objects.filter(is_deleted=False, is_active=True)
        state_id = request.query_params.get("state")
        if state_id:
            rows = rows.filter(state_id=state_id)
        rows = rows.order_by("name")
        return Response([
            {"unique_id": d.unique_id, "name": d.name, "state_id": d.state_id_id}
            for d in rows
        ])

    # ---- GET /publicgrievance/cities/?district=<district id> ----
    @action(detail=False, methods=["get"])
    def cities(self, request):
        district_id = request.query_params.get("district")
        if not district_id:
            return Response([])
        options = []
        for field, model, name_attr in LOCAL_BODY_SOURCES:
            rows = model.objects.filter(is_deleted=False, is_active=True, district_id=district_id)
            options.extend(
                {"unique_id": row.unique_id, "name": getattr(row, name_attr, None), "type": field}
                for row in rows
            )
        options.sort(key=lambda item: (item["name"] or "").lower())
        return Response(options)

    @transaction.atomic
    def create(self, request):
        data = request.data
        person_name = str(data.get("person_name") or data.get("profile_name") or "").strip()
        description = str(data.get("description") or "").strip()
        location_text = str(data.get("location_text") or "").strip()
        device_id = str(data.get("device_id") or "").strip()
        phone = str(data.get("phone") or data.get("wa_phone") or "").strip()
        email = str(data.get("email") or "").strip()
        gender = str(data.get("gender") or "").strip().lower()
        if gender not in dict(ComplaintTicket.GENDER_CHOICES):
            gender = ""
        latitude = _decimal_from_input(data.get("latitude"))
        longitude = _decimal_from_input(data.get("longitude"))

        if email:
            try:
                validate_email(email)
            except ValidationError:
                return Response({"email": "Enter a valid email address."}, status=http_status.HTTP_400_BAD_REQUEST)

        if not person_name:
            return Response({"person_name": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        if not description:
            return Response({"description": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        if latitude is None or longitude is None:
            return Response({"location": "Latitude and longitude are required."}, status=http_status.HTTP_400_BAD_REQUEST)

        waste_type_ids = _multi_values(data, "waste_type")
        waste_types = list(WasteType.objects.filter(
            unique_id__in=waste_type_ids, is_deleted=False, is_active=True
        ))

        # Complaint Type / Sub-Type chosen on the public form.
        selected_category = ComplaintCategory.objects.filter(
            unique_id=data.get("category"), is_deleted=False, is_active=True
        ).first()
        subcategory = ComplaintSubcategory.objects.filter(
            unique_id=data.get("subcategory"), is_deleted=False, is_active=True
        ).first()
        if subcategory and (not selected_category or subcategory.category_id != selected_category.unique_id):
            subcategory = None

        if not waste_types and not selected_category:
            return Response(
                {"waste_type": "Select a complaint type."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Flat geo chosen on the public form: State -> District -> City
        # (city = one of the five local-body masters; `city_type` says which
        # one, otherwise all five are checked).
        state = State.objects.filter(unique_id=data.get("state"), is_deleted=False).first()
        district = District.objects.filter(unique_id=data.get("district"), is_deleted=False).first()
        city_id = data.get("city")
        city_type = str(data.get("city_type") or "").strip()
        local_body_fields = {}
        if city_id:
            for field, model, _ in LOCAL_BODY_SOURCES:
                if city_type and city_type != field:
                    continue
                local_body = model.objects.filter(unique_id=city_id, is_deleted=False).first()
                if local_body:
                    local_body_fields[field] = local_body
                    if not district:
                        district = local_body.district_id
                    break
        if district and not state:
            state = district.state_id

        # Category is required by ComplaintTicket; when the form did not send
        # one (legacy waste-type-only submissions) fall back to OTHER so
        # reporting and the routing/SLA engine still have something to key on.
        category = selected_category or ComplaintCategory.objects.filter(
            category_code="OTHER", is_deleted=False, is_active=True
        ).first()
        if not category:
            category = ComplaintCategory.objects.filter(is_deleted=False, is_active=True).order_by("sort_order").first()
        if not category:
            return Response(
                {"detail": "Complaint categories are not configured. Run the complaint-ticket seeder."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # With multiple waste types selected, the most urgent default
        # priority wins and the first configured default team is used -
        # a ticket can only have one team/priority regardless of how many
        # waste types it covers.
        priority_candidates = [w.default_priority for w in waste_types if w.default_priority_id]
        waste_type_priority = min(priority_candidates, key=lambda p: p.sort_order) if priority_candidates else None
        assigned_team = next((w.default_team for w in waste_types if w.default_team_id), None)
        sla_source = min(
            (w for w in waste_types if w.assign_within_minutes or w.resolve_within_minutes),
            key=_sla_strictness_key,
            default=None,
        )

        priority = (
            waste_type_priority
            or (subcategory.default_priority if subcategory else None)
            or category.default_priority
            or ComplaintPriority.objects.filter(priority_code="P3", is_deleted=False).first()
        )
        status_obj = ComplaintStatus.objects.filter(status_code="SUBMITTED", is_deleted=False).first()
        if not priority or not status_obj:
            return Response(
                {"detail": "Complaint ticket masters are not configured. Run the complaint-ticket seeder."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # The device key is still stored on the ticket for traceability, but the
        # 6-hour same-device cooldown is disabled so citizens can register
        # multiple complaints from one device.
        idempotency_key = f"publicgrievance:{device_id}" if device_id else None
        # cutoff = timezone.now() - PUBLIC_GRIEVANCE_DUPLICATE_WINDOW
        # duplicate = None
        # if idempotency_key:
        #     duplicate = ComplaintTicket.objects.filter(
        #         idempotency_key=idempotency_key,
        #         is_deleted=False,
        #         created__gte=cutoff,
        #     ).order_by("-created").first()
        # if duplicate:
        #     return Response(
        #         {
        #             "detail": "A public grievance was already submitted from this device. Please try again after 6 hours.",
        #             "ticket_no": duplicate.ticket_no,
        #             "unique_id": duplicate.unique_id,
        #         },
        #         status=http_status.HTTP_409_CONFLICT,
        #     )

        source, _ = ComplaintSource.objects.get_or_create(
            source_code="PUBLIC_GRIEVANCE",
            defaults={"source_name": "Public Grievance", "is_active": True, "is_deleted": False},
        )
        ticket = ComplaintTicket.objects.create(
            source=source,
            category=category,
            subcategory=subcategory,
            priority=priority,
            status=status_obj,
            profile_name=person_name,
            wa_phone=phone or None,
            email=email or None,
            gender=gender or None,
            title=(description or (subcategory.subcategory_name if subcategory else "") or category.category_name)[:120],
            description=description,
            location_text=location_text,
            latitude=latitude,
            longitude=longitude,
            state=state,
            district=district,
            idempotency_key=idempotency_key,
            assigned_team=assigned_team,
            **local_body_fields,
        )
        ticket.waste_types.set(waste_types)
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

        # The most time-sensitive selected waste type drives SLA timing
        # directly when configured; anything left empty (no waste type here
        # has a resolve/assign SLA configured) falls back to the
        # category-based routing/SLA engine below.
        if sla_source:
            now = timezone.now()
            add_minutes = _add_business_minutes if sla_source.working_hours_only else (
                lambda start, minutes: start + timedelta(minutes=minutes)
            )
            sla_fields = []
            if sla_source.assign_within_minutes:
                ticket.first_response_due_at = add_minutes(now, sla_source.assign_within_minutes)
                sla_fields.append("first_response_due_at")
            if sla_source.resolve_within_minutes:
                ticket.sla_due_at = add_minutes(now, sla_source.resolve_within_minutes)
                sla_fields.append("sla_due_at")
            ticket.save(update_fields=sla_fields)

        apply_routing_and_sla(ticket, save=True)

        if ticket.email:
            transaction.on_commit(
                lambda: send_grievance_confirmation_email(ticket.email, ticket.ticket_no, person_name)
            )

        return Response(
            {
                "message": "Public grievance submitted successfully.",
                "ticket_no": ticket.ticket_no,
                "unique_id": ticket.unique_id,
            },
            status=http_status.HTTP_201_CREATED,
        )

    # ---- GET /publicgrievance/status/?ticket_no=... or ?mobile=... ----
    @action(detail=False, methods=["get"])
    def status(self, request):
        ticket_no = str(request.query_params.get("ticket_no") or "").strip()
        mobile = str(request.query_params.get("mobile") or "").strip()
        if not ticket_no and not mobile:
            return Response(
                {"detail": "Provide a ticket number or mobile number."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            ComplaintTicket.objects.filter(is_deleted=False)
            .select_related("status", "category", "subcategory")
            .prefetch_related("status_history", "status_history__to_status")
        )
        qs = qs.filter(ticket_no__iexact=ticket_no) if ticket_no else qs.filter(wa_phone=mobile)
        tickets = list(qs.order_by("-created")[:20])
        if not tickets:
            return Response({"detail": "No grievance found."}, status=http_status.HTTP_404_NOT_FOUND)

        def timeline_for(ticket):
            entries = [h for h in ticket.status_history.all() if h.visible_to_citizen]
            entries.sort(key=lambda h: h.changed_at)
            return [
                {
                    "status": h.to_status.status_name if h.to_status else None,
                    "status_code": h.to_status.status_code if h.to_status else None,
                    "at": h.changed_at,
                    "remarks": h.remarks or "",
                }
                for h in entries
            ]

        return Response([
            {
                "ticket_no": t.ticket_no,
                "status": t.status.status_name if t.status else None,
                "status_code": t.status.status_code if t.status else None,
                "category": t.category.category_name if t.category else None,
                "subcategory": t.subcategory.subcategory_name if t.subcategory else None,
                "description": t.description,
                "location_text": t.location_text,
                "created": t.created,
                "timeline": timeline_for(t),
            }
            for t in tickets
        ])
