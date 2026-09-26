from django.db import transaction, models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


def _actor_user(request):
    """Return the request user only if it is an auth User.

    Staff log in as `StaffcreationOfficeDetails` (not the auth User model), so
    the history models' *_by_user / assigned_by FKs (-> AUTH_USER_MODEL) must be
    left null for staff actors rather than assigned a Staffcreation instance.
    """
    user = getattr(request, "user", None)
    return user if isinstance(user, User) else None

from rest_framework import filters, status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.complaint_ticket_routing import apply_routing_and_sla, perform_escalation
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope, _resolve_geo_candidate
from app.utils.pagination import LimitOffsetWithPage
from app.utils.roles import is_admin_role, is_supervisor_role
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
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.core_modules.complaint_management.status_history import ComplaintStatusHistory
from app.models.core_modules.complaint_management.assignment_history import ComplaintAssignmentHistory
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
    """Q matching any of the five local-body FK columns against `local_body_id`."""
    return (
        models.Q(corporation_id=local_body_id)
        | models.Q(municipality_id=local_body_id)
        | models.Q(town_panchayat_id=local_body_id)
        | models.Q(panchayat_union_id=local_body_id)
        | models.Q(panchayat_id=local_body_id)
    )


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
    """Tickets explicitly owned by a staff member or their team/department.

    assigned_staff_id is a plain unique_id string; team/department links go
    through ComplaintTeam lookups (no joins from the ticket)."""
    staff_uid = getattr(user, "staff_unique_id", None)
    scope = models.Q(assigned_staff_id=staff_uid) if staff_uid else models.Q(pk__in=[])
    led_team_ids = ComplaintTeam.objects.filter(
        lead_staff_id=staff_uid, is_deleted=False).values("unique_id") if staff_uid else []
    if staff_uid:
        scope = scope | models.Q(assigned_team_id__in=led_team_ids)
    department = getattr(user, "department_id", None)
    # Staffcreation.department_id is itself an FK field literally named
    # `department_id`, so `department` here may be an instance or a raw id.
    dept_uid = getattr(department, "unique_id", department)
    if dept_uid:
        dept_team_ids = ComplaintTeam.objects.filter(
            department_id=dept_uid, is_deleted=False).values("unique_id")
        return scope | models.Q(assigned_team_id__in=dept_team_ids)

    department_name = (getattr(user, "department", "") or "").strip()
    if department_name:
        from app.models.masters.department import Department
        dept_ids = Department.objects.filter(
            department_name__iexact=department_name,
            is_deleted=False).values("unique_id")
        dept_team_ids = ComplaintTeam.objects.filter(
            department_id__in=dept_ids, is_deleted=False).values("unique_id")
        return scope | models.Q(assigned_team_id__in=dept_team_ids)
    return scope


class ComplaintTicketViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_ticket"
    serializer_class = ComplaintTicketSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["ticket_no", "wa_phone", "profile_name", "title", "description"]
    ordering_fields = ["created", "updated", "sla_due_at", "ticket_no"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "tickets"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ComplaintTicketDetailSerializer
        return ComplaintTicketSerializer

    def get_queryset(self):
        # Converted FKs are plain CharFields — no select_related possible.
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
            state = params.get("state")
            if state:
                qs = qs.filter(state_id=state)
            district = params.get("district")
            if district:
                qs = qs.filter(district_id=district)
            area_type = params.get("area_type") or params.get("area_type_id")
            if area_type:
                qs = qs.filter(area_type_id=area_type)
            city = params.get("city")
            if city:
                qs = qs.filter(_local_body_q(city))
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
        # belong to them - i.e. assigned to them personally, to a team
        # they lead, or to any team in their department. Platform
        # superadmins (and explicit ?all=1) see everything.
        # ----------------------------------------------------------
        user = getattr(self.request, "user", None)
        is_super = getattr(user, "is_superuser", False)
        is_staff_record = hasattr(user, "staff_unique_id")
        wants_all = params.get("all") in ("1", "true", "True")
        if not is_super and not wants_all:
            if is_admin_role(user) or is_supervisor_role(user):
                # Corporation admins/supervisors see every ticket in their
                # corporation subtree (capped by their StaffDataScope). They
                # must also see tickets explicitly routed to them or their
                # team even when the citizen's geo is outside that scope.
                geo_qs = filter_flat_geo_queryset_by_requester_scope(qs, user)
                if is_staff_record:
                    qs = (geo_qs | qs.filter(_staff_ticket_scope(user))).distinct()
                else:
                    qs = geo_qs
            elif is_staff_record:
                # Regular staff still see only tickets that belong to them.
                qs = qs.filter(_staff_ticket_scope(user))
        return qs

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
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
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
        team_id = request.data.get("team")
        staff_id = request.data.get("staff")

        from_team = ticket.assigned_team
        from_staff = ticket.assigned_staff

        new_team = from_team
        if team_id:
            new_team = ComplaintTeam.objects.filter(unique_id=team_id, is_deleted=False).first()
            if not new_team:
                return Response({"team": "Invalid team."}, status=http_status.HTTP_400_BAD_REQUEST)

        # Resolve target staff: explicit staff param, else the team's lead, else unchanged
        new_staff = from_staff
        new_staff_id = ticket.assigned_staff_id
        new_team_id = ticket.assigned_team_id
        if staff_id:
            new_staff = StaffcreationOfficeDetails.objects.filter(staff_unique_id=staff_id).first()
            if not new_staff:
                return Response({"staff": "Invalid staff."}, status=http_status.HTTP_400_BAD_REQUEST)
            new_staff_id = new_staff.staff_unique_id
        elif team_id and new_team and new_team.lead_staff_id:
            new_staff = new_team.lead_staff
            new_staff_id = new_team.lead_staff_id
        if team_id:
            new_team_id = new_team.unique_id if new_team else None

        ticket.assigned_team_id = new_team_id
        ticket.assigned_staff_id = new_staff_id
        ticket.save(update_fields=["assigned_team_id", "assigned_staff_id"])

        ComplaintAssignmentHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_team_id=getattr(from_team, "unique_id", None),
            to_team_id=getattr(new_team, "unique_id", None),
            from_staff_id=getattr(from_staff, "staff_unique_id", None),
            to_staff_id=getattr(new_staff, "staff_unique_id", None),
            assigned_by_id=getattr(_actor_user(request), "unique_id", None),
            assignment_reason=request.data.get("reason"),
        )
        if new_staff and (not from_staff or new_staff.staff_unique_id != from_staff.staff_unique_id):
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
            # requested district OR whose local-body FK equals the requested
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
        if note:
            ComplaintComment.objects.create(
                ticket_id=ticket.unique_id,
                comment_by_user_id=getattr(_actor_user(request), "unique_id", None),
                comment_text=note,
                is_internal=False,
            )
        if ticket.assigned_staff:
            notification_service.notify(
                ticket,
                "RESOLVED",
                f"Ticket {ticket.ticket_no} has been marked resolved." + (f" Note: {note}" if note else ""),
                staff=ticket.assigned_staff,
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
    @transaction.atomic
    def escalate(self, request, unique_id=None):
        ticket = self.get_object()

        # Determine target team: explicit param, else current team's escalates_to
        team_id = request.data.get("team")
        target = None
        if team_id:
            target = ComplaintTeam.objects.filter(unique_id=team_id, is_deleted=False).first()
            if not target:
                return Response({"team": "Invalid team."}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            perform_escalation(
                ticket,
                target_team=target,
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
        if ticket.assigned_staff:
            notification_service.notify(
                ticket,
                "REOPENED",
                f"Ticket {ticket.ticket_no} has been reopened." + (
                    f" Reason: {request.data.get('reopen_reason')}" if request.data.get("reopen_reason") else ""
                ),
                staff=ticket.assigned_staff,
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
