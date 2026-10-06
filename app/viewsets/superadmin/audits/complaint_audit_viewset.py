from datetime import datetime, time, timedelta

from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintEscalationHistory,
    ComplaintStatus,
    ComplaintTicket,
)
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.services.complaint_audit import LOCAL_BODY_SOURCES, summarize_tickets, ticket_timeline
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.core_modules.complaint_management.ticket_viewset import (
    _area_type_q,
    _local_body_q,
    scope_tickets_to_requester,
)


def _start_of_day(day):
    # Aware day bounds instead of `created__date__*`: on MySQL without
    # loaded timezone tables CONVERT_TZ yields NULL and matches nothing.
    return timezone.make_aware(datetime.combine(day, time.min))


def _options(rows):
    return sorted(
        ({"unique_id": uid, "name": name or uid} for uid, name in rows),
        key=lambda o: o["name"].lower(),
    )


class ComplaintAuditViewSet(viewsets.ViewSet):
    """
    Read-only Complaint Audit: per ticket, when it was raised, how it was
    resolved (resolution remarks), why it was reopened, its escalations and
    how long it took. Assembled on read by app.services.complaint_audit from
    the ticket's history rows; deleted tickets are included so they stay
    visible in the audit.
    """

    permission_classes = [IsAuthenticated]
    # Matches the "complaint-audit" screen in the "audits" module of
    # app/utils/permission_catalog.py.
    permission_resource = "ComplaintAudit"
    lookup_field = "unique_id"

    def _scoped_base_queryset(self):
        """Ticket visibility gate, the same one the complaint ticket list
        uses (scope_tickets_to_requester): a platform super admin sees every
        ticket; an admin/supervisor their area (plus tickets routed or
        escalated to them); other staff only tickets they hold or held."""
        queryset = ComplaintTicket.objects.all().order_by("-created", "-pk")
        return scope_tickets_to_requester(queryset, getattr(self.request, "user", None))

    def get_queryset(self):
        queryset = self._scoped_base_queryset()
        params = self.request.query_params

        state = params.get("state") or params.get("state_id")
        if state:
            queryset = queryset.filter(state_id=state)

        district = params.get("district") or params.get("district_id")
        if district:
            queryset = queryset.filter(district_id=district)

        area_type = params.get("area_type") or params.get("area_type_id")
        if area_type:
            queryset = queryset.filter(_area_type_q(area_type))

        # Any of the five local-body columns (the ticket's "city"), matching
        # the complaint ticket list's ?city= filter.
        city = params.get("city") or params.get("local_body")
        if city:
            queryset = queryset.filter(_local_body_q(city))

        status_codes = [c for c in (params.get("status") or "").upper().split(",") if c]
        if status_codes:
            status_ids = ComplaintStatus.objects.filter(status_code__in=status_codes).values("unique_id")
            queryset = queryset.filter(status_id__in=status_ids)

        category = params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)

        if params.get("reopened") in ("1", "true"):
            queryset = queryset.filter(reopened_count__gt=0)

        if params.get("escalated") in ("1", "true"):
            escalated_ids = ComplaintEscalationHistory.objects.filter(is_deleted=False).values("ticket_id")
            queryset = queryset.filter(unique_id__in=escalated_ids)

        deleted = params.get("deleted")
        if deleted == "only":
            queryset = queryset.filter(is_deleted=True)
        elif deleted == "exclude":
            queryset = queryset.filter(is_deleted=False)

        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(created__gte=_start_of_day(date_from))

        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(created__lt=_start_of_day(date_to + timedelta(days=1)))

        search = (params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(ticket_no__icontains=search)
                | Q(title__icontains=search)
                | Q(profile_name__icontains=search)
                | Q(wa_phone__icontains=search)
            )

        return queryset

    def list(self, request):
        queryset = self.get_queryset()
        paginator = LimitOffsetWithPage()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is None:
            return Response(summarize_tickets(queryset))
        return paginator.get_paginated_response(summarize_tickets(page))

    def retrieve(self, request, unique_id=None):
        ticket = self._scoped_base_queryset().filter(unique_id=unique_id).first()
        if ticket is None:
            raise Http404
        return Response({**summarize_tickets([ticket])[0], **ticket_timeline(ticket)})

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """State / district / local body / status / category choices for the
        list page's dropdowns. Geo options come from the scoped tickets, so a
        user is never offered an area they cannot see; districts narrow to
        ?state= and local bodies to ?district=."""
        unordered = self._scoped_base_queryset().order_by()
        params = request.query_params
        state_id = params.get("state")
        district_id = params.get("district")
        district_source = unordered.filter(state_id=state_id) if state_id else unordered
        local_body_source = district_source.filter(district_id=district_id) if district_id else district_source

        def ids(source, field):
            return [v for v in source.values_list(field, flat=True).distinct() if v]

        local_bodies = []
        for field, model, name_attr, label in LOCAL_BODY_SOURCES:
            local_bodies.extend(
                {"unique_id": uid, "name": name or uid, "type": label}
                for uid, name in model.objects.filter(
                    unique_id__in=ids(local_body_source, field)
                ).values_list("unique_id", name_attr)
            )
        local_bodies.sort(key=lambda o: o["name"].lower())

        return Response({
            "states": _options(
                State.objects.filter(unique_id__in=ids(unordered, "state_id")).values_list("unique_id", "name")
            ),
            "districts": _options(
                District.objects.filter(unique_id__in=ids(district_source, "district_id")).values_list("unique_id", "name")
            ),
            "local_bodies": local_bodies,
            "statuses": [
                {"unique_id": code, "name": name}
                for code, name in ComplaintStatus.objects.filter(is_deleted=False)
                .order_by("sort_order")
                .values_list("status_code", "status_name")
            ],
            "categories": _options(
                ComplaintCategory.objects.filter(
                    unique_id__in=ids(unordered, "category_id")
                ).values_list("unique_id", "category_name")
            ),
        })
