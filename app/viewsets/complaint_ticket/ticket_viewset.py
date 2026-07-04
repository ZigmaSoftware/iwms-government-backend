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

from rest_framework import status as http_status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.complaint_ticket_routing import apply_routing_and_sla

from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.complaint_ticket.status_master import ComplaintStatus
from app.models.complaint_ticket.team_master import ComplaintTeam
from app.models.complaint_ticket.status_history import ComplaintStatusHistory
from app.models.complaint_ticket.assignment_history import ComplaintAssignmentHistory
from app.models.complaint_ticket.escalation_history import ComplaintEscalationHistory
from app.models.complaint_ticket.comment import ComplaintComment
from app.models.complaint_ticket.reopen_history import ComplaintReopenHistory
from app.models.complaint_ticket.feedback import ComplaintFeedback
from app.models.complaint_ticket.ticket_attachment import ComplaintAttachment
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails

from app.serializers.complaint_ticket.transaction_serializers import (
    ComplaintTicketSerializer,
    ComplaintTicketDetailSerializer,
    ComplaintCommentSerializer,
    ComplaintAttachmentSerializer,
    ComplaintFeedbackSerializer,
)


def _resolve_status(status_code):
    return ComplaintStatus.objects.filter(status_code=status_code, is_deleted=False).first()


def _status_bucket_q(bucket):
    if bucket == "pending":
        return models.Q(status__status_code__in=["SUBMITTED", "ASSIGNED"])
    if bucket == "started":
        return models.Q(status__status_code="IN_PROGRESS")
    if bucket == "escalated":
        return models.Q(status__status_code="ESCALATED")
    if bucket == "resolved":
        return models.Q(status__status_code__in=["RESOLVED", "CLOSED", "REJECTED", "CANCELLED"])
    if bucket == "open":
        return ~models.Q(status__status_code__in=["RESOLVED", "CLOSED", "REJECTED", "CANCELLED"])
    return models.Q()


class ComplaintTicketViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintTicketSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "tickets"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ComplaintTicketDetailSerializer
        return ComplaintTicketSerializer

    def get_queryset(self):
        qs = ComplaintTicket.objects.filter(is_deleted=False).select_related(
            "category", "subcategory", "priority", "status", "source",
            "customer", "assigned_team", "assigned_team__department",
            "assigned_staff", "location_node",
        ).prefetch_related(
            "status_history", "status_history__to_status",
            "escalation_history", "escalation_history__escalated_to_team",
            "escalation_history__escalated_from_team",
        ).order_by("-created")
        params = self.request.query_params
        customer = params.get("customer") or params.get("customer_id")
        if customer:
            qs = qs.filter(customer_id=customer)
        wa_phone = params.get("wa_phone")
        if wa_phone:
            qs = qs.filter(wa_phone=wa_phone)
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
                qs = qs.filter(status__status_code=status_code)

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
        if is_staff_record and not is_super and not wants_all:
            scope = models.Q(assigned_staff=user) | models.Q(assigned_team__lead_staff=user)
            department = getattr(user, "department_id", None)
            if department:
                scope = scope | models.Q(assigned_team__department=department)
            else:
                department_name = (getattr(user, "department", "") or "").strip()
                if department_name:
                    scope = scope | models.Q(
                        assigned_team__department__department_name__iexact=department_name
                    )
            qs = qs.filter(scope)
        return qs

    # ----------------------------------------------------------
    # CREATE - derive routing + SLA after the base create
    # ----------------------------------------------------------
    def perform_create(self, serializer):
        super().perform_create(serializer)  # audit
        ticket = serializer.instance
        # Record initial status history
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=ticket.status,
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
        ticket.status = new_status
        if new_status.status_code == "RESOLVED" and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        if new_status.status_code == "CLOSED" and not ticket.closed_at:
            ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "resolved_at", "closed_at"])

        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=old_status,
            to_status=new_status,
            changed_by_user=_actor_user(request),
            remarks=request.data.get("remarks"),
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
        if staff_id:
            new_staff = StaffcreationOfficeDetails.objects.filter(staff_unique_id=staff_id).first()
            if not new_staff:
                return Response({"staff": "Invalid staff."}, status=http_status.HTTP_400_BAD_REQUEST)
        elif team_id and new_team and new_team.lead_staff_id:
            new_staff = new_team.lead_staff

        ticket.assigned_team = new_team
        ticket.assigned_staff = new_staff
        ticket.save(update_fields=["assigned_team", "assigned_staff"])

        ComplaintAssignmentHistory.objects.create(
            ticket=ticket,
            from_team=from_team,
            to_team=new_team,
            from_staff=from_staff,
            to_staff=new_staff,
            assigned_by=_actor_user(request),
            assignment_reason=request.data.get("reason"),
        )
        return Response(self.get_serializer(ticket).data)

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
        ticket.status = resolved_status
        if not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "resolved_at"])

        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=old_status,
            to_status=resolved_status,
            changed_by_user=_actor_user(request),
            remarks=note or "Marked as resolved",
            visible_to_citizen=True,
        )
        if note:
            ComplaintComment.objects.create(
                ticket=ticket,
                comment_by_user=_actor_user(request),
                comment_text=note,
                is_internal=False,
            )
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # POST /tickets/{id}/escalate/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="escalate")
    @transaction.atomic
    def escalate(self, request, unique_id=None):
        ticket = self.get_object()
        current_team = ticket.assigned_team

        # Determine target team: explicit param, else current team's escalates_to
        team_id = request.data.get("team")
        if team_id:
            target = ComplaintTeam.objects.filter(unique_id=team_id, is_deleted=False).first()
            if not target:
                return Response({"team": "Invalid team."}, status=http_status.HTTP_400_BAD_REQUEST)
        else:
            target = current_team.escalates_to if current_team else None

        if not target:
            return Response(
                {"detail": "Already at the top of the escalation chain."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        escalated_status = _resolve_status("ESCALATED")

        from_team = current_team
        from_staff = ticket.assigned_staff

        # Next escalation level
        last_level = (
            ticket.escalation_history.aggregate(m=models.Max("escalation_level"))["m"]
            if hasattr(ticket, "escalation_history") else None
        )
        base_level = last_level or (current_team.escalation_level if current_team else 1)
        next_level = base_level + 1

        ticket.assigned_team = target
        ticket.assigned_staff = target.lead_staff
        if escalated_status:
            old_status = ticket.status
            ticket.status = escalated_status
            ticket.save(update_fields=["assigned_team", "assigned_staff", "status"])
        else:
            old_status = ticket.status
            ticket.save(update_fields=["assigned_team", "assigned_staff"])

        reason = request.data.get("reason")

        ComplaintEscalationHistory.objects.create(
            ticket=ticket,
            escalation_level=next_level,
            escalated_from_team=from_team,
            escalated_to_team=target,
            escalated_to_staff=target.lead_staff,
            reason=reason,
            escalated_by_system=False,
        )
        ComplaintAssignmentHistory.objects.create(
            ticket=ticket,
            from_team=from_team,
            to_team=target,
            from_staff=from_staff,
            to_staff=target.lead_staff,
            assigned_by=_actor_user(request),
            assignment_reason=reason or "Escalated",
        )
        if escalated_status:
            ComplaintStatusHistory.objects.create(
                ticket=ticket,
                from_status=old_status,
                to_status=escalated_status,
                changed_by_user=_actor_user(request),
                remarks=f"Escalated to {target.team_name}" + (f": {reason}" if reason else ""),
                visible_to_citizen=True,
            )
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # POST /tickets/{id}/comments/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="comments")
    def add_comment(self, request, unique_id=None):
        ticket = self.get_object()
        comment = ComplaintComment.objects.create(
            ticket=ticket,
            comment_by_user=_actor_user(request),
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
            ticket=ticket,
            uploaded_by_user=_actor_user(request),
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
        ticket.status = reopened_status
        ticket.reopened_count = (ticket.reopened_count or 0) + 1
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.save(update_fields=["status", "reopened_count", "resolved_at", "closed_at"])

        ComplaintReopenHistory.objects.create(
            ticket=ticket,
            reopened_by_user=_actor_user(request),
            reopen_reason=request.data.get("reopen_reason"),
            previous_status=previous_status,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=previous_status,
            to_status=reopened_status,
            changed_by_user=_actor_user(request),
            remarks="Reopened",
        )
        return Response(self.get_serializer(ticket).data)

    # ----------------------------------------------------------
    # POST /tickets/{id}/feedback/
    # ----------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="feedback")
    def submit_feedback(self, request, unique_id=None):
        ticket = self.get_object()
        feedback, _ = ComplaintFeedback.objects.update_or_create(
            ticket=ticket,
            defaults={
                "customer": ticket.customer,
                "rating": request.data.get("rating"),
                "feedback_text": request.data.get("feedback_text"),
                "is_issue_solved": bool(request.data.get("is_issue_solved", False)),
            },
        )
        return Response(ComplaintFeedbackSerializer(feedback).data, status=http_status.HTTP_201_CREATED)
