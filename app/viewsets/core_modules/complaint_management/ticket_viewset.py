from django.db import transaction, models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


def _actor_user(request):
    """Return the request user only if it is an auth User.

    Staff log in as `StaffcreationOfficeDetails` (not the auth User model), so
    the history models' *_by_user / assigned_by fields (-> AUTH_USER_MODEL) must be
    left null for staff actors rather than assigned a Staffcreation instance.
    """
    user = getattr(request, "user", None)
    return user if isinstance(user, User) else None

from rest_framework import filters, status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.complaint_ticket_routing import apply_routing_and_sla
from app.services.complaint_escalation import (
    CLOSED_STATUS_CODES,
    escalate_ticket,
    is_passed_over,
    restart_escalation_clock,
    stop_escalation_clock,
)
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope, _resolve_geo_candidate
from app.utils.pagination import LimitOffsetWithPage
from app.utils.roles import is_admin_role, is_super_admin, is_supervisor_role
from app.services import notification_service
from app.services.push_notification_service import send_push_to_customer

from app.models.masters.district import District
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat

from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.status_history import ComplaintStatusHistory
from app.models.core_modules.complaint_management.assignment_history import ComplaintAssignmentHistory
from app.models.core_modules.complaint_management.escalation_history import ComplaintEscalationHistory
from app.models.core_modules.complaint_management.comment import ComplaintComment
from app.models.core_modules.complaint_management.reopen_history import ComplaintReopenHistory
from app.models.core_modules.complaint_management.feedback import ComplaintFeedback
from app.models.core_modules.complaint_management.ticket_attachment import ComplaintAttachment
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails

from app.serializers.core_modules.complaint_management.transaction_serializers import (
    ComplaintTicketSerializer,
    ComplaintTicketDetailSerializer,
    ComplaintCommentSerializer,
    ComplaintAttachmentSerializer,
    ComplaintFeedbackSerializer,
)


def _resolve_status(status_code):
    return ComplaintStatus.objects.filter(status_code=status_code, is_deleted=False).first()


# (model, name attribute) of the flat local-body masters - the "city" level
# right below District, mirroring the columns on StaffcreationOfficeDetails.
LOCAL_BODY_SOURCES = (
    (Corporation, "corporation_name"),
    (Municipality, "municipality_name"),
    (TownPanchayat, "town_panchayat_name"),
    (PanchayatUnion, "union_name"),
    (Panchayat, "panchayat_name"),
)


def _find_local_body(local_body_id):
    """Resolve a local-body id against all five flat masters. Returns
    (instance, display_name) or (None, None)."""
    if not local_body_id:
        return None, None
    for model, name_attr in LOCAL_BODY_SOURCES:
        obj = model.objects.filter(unique_id=local_body_id, is_deleted=False).first()
        if obj:
            return obj, getattr(obj, name_attr, None)
    return None, None


def _local_body_q(local_body_id):
    """Q matching any of the five local-body columns against `local_body_id`."""
    return (
        models.Q(corporation_id=local_body_id)
        | models.Q(municipality_id=local_body_id)
        | models.Q(town_panchayat_id=local_body_id)
        | models.Q(panchayat_union_id=local_body_id)
        | models.Q(panchayat_id=local_body_id)
    )


def _area_type_q(area_type_id):
    """Tickets in an area type (Urban / Rural Local Body). Older tickets were
    saved with only their local body, so also match any ticket whose local
    body belongs to that area type."""
    q = models.Q(area_type_id=area_type_id)
    for model, field in (
        (Corporation, "corporation_id"),
        (Municipality, "municipality_id"),
        (TownPanchayat, "town_panchayat_id"),
        (PanchayatUnion, "panchayat_union_id"),
        (Panchayat, "panchayat_id"),
    ):
        q |= models.Q(**{f"{field}__in": model.objects.filter(area_type_id=area_type_id).values("unique_id")})
    return q


def _status_bucket_q(bucket):
    # status is a plain unique_id string (no DB relation) — resolve via
    # subquery instead of a join.
    if bucket == "pending":
        return models.Q(status_id__in=ComplaintStatus.objects.filter(
            status_code__in=["SUBMITTED", "ASSIGNED"], is_deleted=False).values("unique_id"))
    if bucket == "started":
        return models.Q(status_id__in=ComplaintStatus.objects.filter(
            status_code="IN_PROGRESS", is_deleted=False).values("unique_id"))
    if bucket == "escalated":
        return models.Q(status_id__in=ComplaintStatus.objects.filter(
            status_code="ESCALATED", is_deleted=False).values("unique_id"))
    if bucket == "resolved":
        return models.Q(status_id__in=ComplaintStatus.objects.filter(
            status_code__in=["RESOLVED", "CLOSED", "REJECTED", "CANCELLED"],
            is_deleted=False).values("unique_id"))
    if bucket == "open":
        return ~models.Q(status_id__in=ComplaintStatus.objects.filter(
            status_code__in=["RESOLVED", "CLOSED", "REJECTED", "CANCELLED"],
            is_deleted=False).values("unique_id"))
    return models.Q()


def _public_grievance_source_ids():
    from app.models.core_modules.complaint_management.source_master import ComplaintSource
    return ComplaintSource.objects.filter(
        source_code="PUBLIC_GRIEVANCE", is_deleted=False).values("unique_id")


def _staff_ticket_scope(user):
    """Tickets a staff member is or was responsible for: assigned to them,
    currently escalated to them, or escalated through them earlier (so a
    ticket doesn't vanish from a supervisor's view once it hops further up)."""
    staff_uid = getattr(user, "staff_unique_id", None)
    if not staff_uid:
        return models.Q(pk__in=[])
    escalated_through = ComplaintEscalationHistory.objects.filter(
        models.Q(escalated_to_staff_id=staff_uid) | models.Q(escalated_from_staff_id=staff_uid),
        is_deleted=False,
    ).values("ticket_id")
    return (
        models.Q(assigned_staff_id=staff_uid)
        | models.Q(escalated_to_staff_id=staff_uid)
        | models.Q(unique_id__in=escalated_through)
    )


def scope_tickets_to_requester(qs, user):
    """Tickets `user` may see: everything for a platform super admin; their
    area (capped by their StaffDataScope) plus their own tickets for an
    admin/supervisor; otherwise only tickets they hold or held."""
    if getattr(user, "is_superuser", False):
        return qs
    is_staff_record = hasattr(user, "staff_unique_id")
    if is_admin_role(user) or is_supervisor_role(user):
        # They must also see tickets explicitly routed or escalated to them
        # even when the citizen's geo is outside their scope.
        geo_qs = filter_flat_geo_queryset_by_requester_scope(qs, user)
        if is_staff_record:
            return (geo_qs | qs.filter(_staff_ticket_scope(user))).distinct()
        return geo_qs
    if is_staff_record:
        return qs.filter(_staff_ticket_scope(user))
    return qs


PASSED_OVER_DETAIL = (
    "This ticket has been escalated to a higher level ({level}). You can view it, "
    "but only the staff it is escalated to can act on it."
)


class ComplaintTicketViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_ticket"
    serializer_class = ComplaintTicketSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["ticket_no", "wa_phone", "profile_name", "title", "description"]
    ordering_fields = ["created", "updated", "next_escalation_due_at", "ticket_no"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "tickets"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ComplaintTicketDetailSerializer
        return ComplaintTicketSerializer

    # Actions only the level a ticket currently sits with may take; staff it
    # has escalated past can still view it and add comments/attachments.
    OWNER_ONLY_ACTIONS = {"change_status", "assign", "resolve", "escalate", "reopen", "update", "partial_update", "destroy"}

    def get_object(self):
        ticket = super().get_object()
        if self.action in self.OWNER_ONLY_ACTIONS and is_passed_over(ticket, self.request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(PASSED_OVER_DETAIL.format(
                level=getattr(ticket.escalated_to_staff, "employee_name", None) or f"L{ticket.escalation_level}"
            ))
        return ticket

    def get_queryset(self):
        # Converted relation fields are plain CharFields — no select_related possible.
        # status/escalation histories, attachments and extra details are now
        # plain-string reverse @properties (no prefetch possible).
        qs = ComplaintTicket.objects.filter(is_deleted=False).order_by("-created")
        params = self.request.query_params

        # ----------------------------------------------------------
        # List-only filters. These read query params (customer, district,
        # city, status, ...) that detail actions also legitimately receive
        # for their OWN purposes - e.g. assignable-staff takes a
        # ?district=/?city= to scope the STAFF list, not the ticket being
        # fetched. Applying these here unconditionally would filter the
        # very ticket a detail action is trying to load right out of the
        # queryset, so they only run for the list action (and the "counts"
        # aggregate action below, which needs the exact same scoping so its
        # tab counts match what the list itself would show).
        # ----------------------------------------------------------
        if self.action in ("list", "counts"):
            customer = params.get("customer") or params.get("customer_id")
            if customer:
                qs = qs.filter(customer_id=customer)
            wa_phone = params.get("wa_phone")
            if wa_phone:
                qs = qs.filter(wa_phone=wa_phone)
            # Geo: the legacy ?state=/?district=/?city= names and the flat
            # ?state_id=/.../?panchayat_id= params of the list page's
            # Filters panel (useHierarchyFilter).
            state = params.get("state") or params.get("state_id")
            if state:
                qs = qs.filter(state_id=state)
            district = params.get("district") or params.get("district_id")
            if district:
                qs = qs.filter(district_id=district)
            area_type = params.get("area_type") or params.get("area_type_id")
            if area_type:
                qs = qs.filter(_area_type_q(area_type))
            city = params.get("city")
            if city:
                qs = qs.filter(_local_body_q(city))
            for field in ("corporation_id", "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id"):
                local_body = params.get(field)
                if local_body:
                    qs = qs.filter(**{field: local_body})
            assigned_staff = params.get("assigned_staff")
            if assigned_staff:
                qs = qs.filter(assigned_staff_id=assigned_staff)
            if params.get("escalated") in ("1", "true", "True"):
                qs = qs.filter(is_escalated=True)
            # My Tasks: tickets the requester owns or owned — assigned to
            # them, escalated to them, or escalated up past them (view only
            # for them) — even for an admin/supervisor who can otherwise see
            # their whole area. A platform super admin owns nothing but
            # oversees everything, so their My Tasks lists every ticket.
            if params.get("mine") in ("1", "true", "True") and not is_super_admin(self.request.user):
                qs = qs.filter(_staff_ticket_scope(self.request.user))
            status_code = params.get("status")
            if status_code:
                normalized = status_code.strip().lower()
                bucket = {
                    "in_progress": "started",
                    "progressing": "started",
                    "processing": "started",
                    "new": "pending",
                }.get(normalized, normalized)
                q = _status_bucket_q(bucket)
                if q:
                    qs = qs.filter(q)
                else:
                    qs = qs.filter(status_id__in=ComplaintStatus.objects.filter(
                        status_code=status_code, is_deleted=False).values("unique_id"))
            # Source tab filter (All / Public Grievance / Internal) — only
            # applied for "list" itself; "counts" always computes all three
            # tab totals in one pass regardless of which tab is selected.
            if self.action == "list":
                source_filter = (params.get("source") or "").strip().lower()
                if source_filter == "public":
                    qs = qs.filter(source_id__in=_public_grievance_source_ids())
                elif source_filter == "internal":
                    qs = qs.exclude(source_id__in=_public_grievance_source_ids())

        # ----------------------------------------------------------
        # Per-staff scoping: a staff member only sees the tickets that
        # belong to them - assigned to them, or escalated to/through them
        # along the Staff Hierarchy. Admins/supervisors also see their whole
        # area. Platform superadmins (and explicit ?all=1) see everything.
        # ----------------------------------------------------------
        if params.get("all") in ("1", "true", "True"):
            return qs
        return scope_tickets_to_requester(qs, getattr(self.request, "user", None))

    # ----------------------------------------------------------
    # GET /tickets/counts/ — All / Public Grievance / Internal tab totals,
    # scoped by the same hierarchy/status filters as the list (but NOT by
    # source itself), so the UI can show all three tab counts at once
    # without fetching every ticket to count them client-side.
    # ----------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="counts")
    def counts(self, request):
        qs = self.get_queryset()
        total = qs.count()
        public = qs.filter(source_id__in=_public_grievance_source_ids()).count()
        return Response({
            "all": total,
            "public": public,
            "internal": total - public,
        })

    # ----------------------------------------------------------
    # CREATE - derive routing + SLA after the base create
    # ----------------------------------------------------------
    def perform_create(self, serializer):
        super().perform_create(serializer)  # audit
        ticket = serializer.instance
        # Record initial status history
        ComplaintStatusHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_status_id=None,
            to_status_id=ticket.status_id,
            changed_by_system=True,
            remarks="Ticket created",
        )
        # Apply routing + SLA (only fills empty fields)
        apply_routing_and_sla(ticket, save=True)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        previous_data = self._serialize_instance(instance)
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        # Logged by hand because this soft delete bypasses perform_destroy;
        # the Complaint Audit timeline reads this DELETE row (who / when).
        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=None,
            success=True,
        )
        return Response({"message": "Ticket deleted successfully"}, status=http_status.HTTP_200_OK)

    # ----------------------------------------------------------
    # PATCH /tickets/{id}/status/
    # ----------------------------------------------------------
    @action(detail=True, methods=["patch", "post"], url_path="status")
    @transaction.atomic
    def change_status(self, request, unique_id=None):
        ticket = self.get_object()
        status_code = request.data.get("status_code") or request.data.get("to_status_code")
        if not status_code:
            return Response({"status_code": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)

        new_status = _resolve_status(status_code)
        if not new_status:
            return Response({"status_code": f"Unknown status '{status_code}'."}, status=http_status.HTTP_400_BAD_REQUEST)

        old_status = ticket.status
        ticket.status_id = new_status.unique_id
        if new_status.status_code == "RESOLVED" and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        if new_status.status_code == "CLOSED" and not ticket.closed_at:
            ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status_id", "resolved_at", "closed_at"])

        ComplaintStatusHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_status_id=getattr(old_status, "unique_id", None),
            to_status_id=new_status.unique_id,
            changed_by_user_id=getattr(_actor_user(request), "unique_id", None),
            remarks=request.data.get("remarks"),
        )
        if new_status.status_code in CLOSED_STATUS_CODES:
            stop_escalation_clock(ticket)
        elif old_status.status_code in CLOSED_STATUS_CODES:
            restart_escalation_clock(ticket)
        if old_status.pk != new_status.pk:
            status_label = new_status.status_name or new_status.status_code
            send_push_to_customer(
                ticket.customer,
                "Grievance update",
                f"Your ticket {ticket.ticket_no} status is now: {status_label}.",
                data={"event": "ticket_status_changed", "ticket_id": str(ticket.unique_id), "status": new_status.status_code},
            )
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # POST /tickets/{id}/assign/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="assign")
    @transaction.atomic
    def assign(self, request, unique_id=None):
        ticket = self.get_object()
        staff_id = request.data.get("staff")
        if not staff_id:
            return Response({"staff": "This field is required."}, status=http_status.HTTP_400_BAD_REQUEST)
        new_staff = StaffcreationOfficeDetails.objects.filter(staff_unique_id=staff_id, is_deleted=False).first()
        if not new_staff:
            return Response({"staff": "Invalid staff."}, status=http_status.HTTP_400_BAD_REQUEST)

        from_staff = ticket.responsible_staff
        if ticket.is_escalated:
            # Reassigning an escalated ticket hands it to someone else at
            # the current level — the escalation stays in place.
            ticket.escalated_to_staff_id = new_staff.staff_unique_id
            ticket.save(update_fields=["escalated_to_staff_id"])
        else:
            ticket.assigned_staff_id = new_staff.staff_unique_id
            ticket.save(update_fields=["assigned_staff_id"])

        ComplaintAssignmentHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_staff_id=getattr(from_staff, "staff_unique_id", None),
            to_staff_id=new_staff.staff_unique_id,
            assigned_by_id=getattr(_actor_user(request), "unique_id", None),
            assignment_reason=request.data.get("reason"),
        )
        if not from_staff or new_staff.staff_unique_id != from_staff.staff_unique_id:
            notification_service.notify(
                ticket,
                "ASSIGNED",
                f"Ticket {ticket.ticket_no} ({ticket.title or ticket.category.category_name}) has been assigned to you.",
                staff=new_staff,
            )
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # GET /tickets/{id}/assignable-staff/
    # ----------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="assignable-staff")
    def assignable_staff(self, request, unique_id=None):
        """Staff options for the Assign dialog, scoped to a district/city.

        Defaults to the ticket's own flat district/local body; the caller
        (staff head) may override with ?district=<district id> and/or
        ?city=<local body id> to browse a different area before assigning.
        """
        ticket = self.get_object()
        params = request.query_params
        district_id = params.get("district")
        city_id = params.get("city")
        if not district_id and not city_id:
            district_id = ticket.district_id
            _, ticket_local_body, _ = ticket.local_body
            city_id = ticket_local_body.unique_id if ticket_local_body else None

        city_obj, city_name = _find_local_body(city_id)
        if city_id and not district_id and city_obj:
            # The local-body masters carry their own district_id (plain
            # unique_id string, no DB relation), so a city-only override
            # still resolves the covering district.
            district_id = getattr(city_obj, "district_id", None)
        district_obj = (
            District.objects.filter(unique_id=district_id).first() if district_id else None
        )

        qs = StaffcreationOfficeDetails.objects.filter(
            is_deleted=False,
            active_status=True,
            login_enabled=True,
        )

        if district_id or city_id:
            # Bidirectional: a staff member tagged to the whole district must
            # still show up when the caller drills into one panchayat/city
            # inside it, same as a staff member tagged to that exact
            # panchayat/local body. Match staff whose district equals the
            # requested district OR whose local-body field equals the requested
            # city/local body — covers both coarser- and finer-scoped staff.
            local_body_filter = _local_body_q(city_id) if city_id else models.Q()
            if district_id and city_id:
                qs = qs.filter(models.Q(district_id=district_id) | local_body_filter)
            elif district_id:
                qs = qs.filter(district_id=district_id)
            else:
                qs = qs.filter(local_body_filter)

        department_id = request.query_params.get("department")
        if department_id:
            qs = qs.filter(department_id__unique_id=department_id)

        qs = qs.order_by("employee_name")

        def _local_body(member):
            # Each local-body master has its own name field (corporation_name,
            # panchayat_name, ...) — there is no common `name` attribute.
            # `district`/`corporation`/etc are plain unique_id strings on
            # StaffcreationOfficeDetails (no DB relation), so resolve each
            # against its owning master.
            for level, field, name_attr in (
                ("Corporation", "corporation", "corporation_name"),
                ("Municipality", "municipality", "municipality_name"),
                ("Town Panchayat", "town_panchayat", "town_panchayat_name"),
                ("Panchayat Union", "panchayat_union", "union_name"),
                ("Panchayat", "panchayat", "panchayat_name"),
            ):
                obj = _resolve_geo_candidate(member, field)
                if obj:
                    return level, getattr(obj, name_attr, None) or getattr(obj, "name", None)
            return None, None

        data = []
        for member in qs[:200]:
            level_name, local_body_name = _local_body(member)
            member_district = District.objects.filter(unique_id=member.district_id).first()
            data.append({
                "staff_unique_id": member.staff_unique_id,
                "employee_name": member.employee_name,
                "department_name": getattr(member.department_id, "department_name", None),
                "district_name": getattr(member_district, "name", None),
                "local_body_name": local_body_name,
                "location_level_name": level_name or ("District" if member.district_id else None),
            })

        return Response({
            "district_id": district_id,
            "district_name": getattr(district_obj, "name", None),
            "city_id": city_id if city_obj else None,
            "city_name": city_name,
            "count": len(data),
            "staff": data,
        })

    # ----------------------------------------------------------
    # POST /tickets/{id}/resolve/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="resolve")
    @transaction.atomic
    def resolve(self, request, unique_id=None):
        ticket = self.get_object()
        resolved_status = _resolve_status("RESOLVED")
        if not resolved_status:
            return Response({"detail": "RESOLVED status not configured."}, status=http_status.HTTP_400_BAD_REQUEST)

        note = request.data.get("resolution_note") or request.data.get("remarks")
        old_status = ticket.status
        ticket.status_id = resolved_status.unique_id
        if not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status_id", "resolved_at"])

        ComplaintStatusHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_status_id=getattr(old_status, "unique_id", None),
            to_status_id=resolved_status.unique_id,
            changed_by_user_id=getattr(_actor_user(request), "unique_id", None),
            remarks=note or "Marked as resolved",
            visible_to_citizen=True,
        )
        stop_escalation_clock(ticket)
        if note:
            ComplaintComment.objects.create(
                ticket_id=ticket.unique_id,
                comment_by_user_id=getattr(_actor_user(request), "unique_id", None),
                comment_text=note,
                is_internal=False,
            )
        if ticket.responsible_staff:
            notification_service.notify(
                ticket,
                "RESOLVED",
                f"Ticket {ticket.ticket_no} has been marked resolved." + (f" Note: {note}" if note else ""),
                staff=ticket.responsible_staff,
            )
        send_push_to_customer(
            ticket.customer,
            "Grievance update",
            f"Good news — your ticket {ticket.ticket_no} has been resolved." + (f" {note}" if note else ""),
            data={"event": "ticket_resolved", "ticket_id": str(ticket.unique_id)},
        )
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # POST /tickets/{id}/escalate/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="escalate")
    def escalate(self, request, unique_id=None):
        """Manually hop the ticket to the next enabled Staff Hierarchy level
        — the same move the SLA sweep makes on breach."""
        ticket = self.get_object()
        if ticket.status and ticket.status.status_code in CLOSED_STATUS_CODES:
            return Response({"detail": "A closed ticket cannot be escalated."}, status=http_status.HTTP_400_BAD_REQUEST)
        try:
            ticket = escalate_ticket(
                ticket,
                reason=request.data.get("reason"),
                actor_user=_actor_user(request),
                by_system=False,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # POST /tickets/{id}/comments/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="comments")
    def add_comment(self, request, unique_id=None):
        ticket = self.get_object()
        comment = ComplaintComment.objects.create(
            ticket_id=ticket.unique_id,
            comment_by_user_id=getattr(_actor_user(request), "unique_id", None),
            comment_text=request.data.get("comment_text", ""),
            is_internal=bool(request.data.get("is_internal", False)),
            is_sensitive=bool(request.data.get("is_sensitive", False)),
        )
        return Response(ComplaintCommentSerializer(comment).data, status=http_status.HTTP_201_CREATED)

    # ----------------------------------------------------------
    # POST /tickets/{id}/attachments/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="attachments")
    def add_attachment(self, request, unique_id=None):
        ticket = self.get_object()
        attachment = ComplaintAttachment.objects.create(
            ticket_id=ticket.unique_id,
            uploaded_by_user_id=getattr(_actor_user(request), "unique_id", None),
            file=request.data.get("file"),
            file_name=request.data.get("file_name"),
            file_type=request.data.get("file_type"),
            mime_type=request.data.get("mime_type"),
        )
        return Response(
            ComplaintAttachmentSerializer(attachment, context={"request": request}).data,
            status=http_status.HTTP_201_CREATED,
        )

    # ----------------------------------------------------------
    # POST /tickets/{id}/reopen/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="reopen")
    @transaction.atomic
    def reopen(self, request, unique_id=None):
        ticket = self.get_object()
        if not ticket.status.allow_reopen:
            return Response(
                {"detail": "Current status does not allow reopen."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        reopened_status = _resolve_status("REOPENED")
        if not reopened_status:
            return Response({"detail": "REOPENED status not configured."}, status=http_status.HTTP_400_BAD_REQUEST)

        previous_status = ticket.status
        ticket.status_id = reopened_status.unique_id
        ticket.reopened_count = (ticket.reopened_count or 0) + 1
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.save(update_fields=["status_id", "reopened_count", "resolved_at", "closed_at"])

        ComplaintReopenHistory.objects.create(
            ticket_id=ticket.unique_id,
            reopened_by_user_id=getattr(_actor_user(request), "unique_id", None),
            reopen_reason=request.data.get("reopen_reason"),
            previous_status_id=getattr(previous_status, "unique_id", None),
        )
        ComplaintStatusHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_status_id=getattr(previous_status, "unique_id", None),
            to_status_id=reopened_status.unique_id,
            changed_by_user_id=getattr(_actor_user(request), "unique_id", None),
            remarks="Reopened",
        )
        restart_escalation_clock(ticket)
        if ticket.responsible_staff:
            notification_service.notify(
                ticket,
                "REOPENED",
                f"Ticket {ticket.ticket_no} has been reopened." + (
                    f" Reason: {request.data.get('reopen_reason')}" if request.data.get("reopen_reason") else ""
                ),
                staff=ticket.responsible_staff,
            )
        send_push_to_customer(
            ticket.customer,
            "Grievance update",
            f"Your ticket {ticket.ticket_no} has been reopened and is being looked at again.",
            data={"event": "ticket_reopened", "ticket_id": str(ticket.unique_id)},
        )
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # POST /tickets/{id}/feedback/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="feedback")
    def submit_feedback(self, request, unique_id=None):
        ticket = self.get_object()
        feedback, _ = ComplaintFeedback.objects.update_or_create(
            ticket_id=ticket.unique_id,
            defaults={
                "customer_id": ticket.customer_id,
                "rating": request.data.get("rating"),
                "feedback_text": request.data.get("feedback_text"),
                "is_issue_solved": bool(request.data.get("is_issue_solved", False)),
            },
        )
        return Response(ComplaintFeedbackSerializer(feedback).data, status=http_status.HTTP_201_CREATED)
