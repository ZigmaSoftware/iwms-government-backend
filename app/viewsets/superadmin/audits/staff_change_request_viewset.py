from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.superadmin.audits.staff_change_request import StaffChangeRequest
from app.models.superadmin.staff_management.staffcreation import (
    Staffcreation,
    StaffPersonalDetails,
)
from app.serializers.superadmin.audits.staff_change_request_serializer import (
    StaffChangeRequestCreateSerializer,
    StaffChangeRequestDecisionSerializer,
    StaffChangeRequestSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin


class StaffChangeRequestViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """Staff self-service requests to change one of their own
    StaffPersonalDetails fields, subject to their supervisor's approval.

    - list/retrieve: a staff member sees their own requests; anyone who is
      another staff member's resolved approver (staff_head_id) also sees
      requests routed to them via ?scope=pending_approval.
    - create: submits a new request for the current authenticated staff
      member; approver_id and old_value are resolved server-side.
    - approve/reject: only callable by the request's resolved approver_id
      (or a super_admin), applies new_value to StaffPersonalDetails on
      approval inside a transaction.
    """

    throttle_scope = "staff_change_request"
    permission_classes = [IsAuthenticated]
    serializer_class = StaffChangeRequestSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "audits"
    AUDIT_ENDPOINT = "staff-change-requests"

    def _current_staff(self):
        user = self.request.user
        if isinstance(user, Staffcreation):
            return user
        unique_id = getattr(user, "staff_unique_id", None)
        if unique_id:
            return Staffcreation.objects.filter(
                staff_unique_id=unique_id, is_deleted=False
            ).first()
        return None

    def get_queryset(self):
        queryset = StaffChangeRequest.objects.all()
        staff = self._current_staff()
        if staff is None:
            return queryset.none()

        scope = self.request.query_params.get("scope")
        if scope == "pending_approval":
            return queryset.filter(
                approver_id=staff.staff_unique_id, status=StaffChangeRequest.Status.PENDING
            )

        if getattr(self.request.user, "is_superuser", False):
            return queryset

        return queryset.filter(requested_by_id=staff.staff_unique_id)

    def create(self, request, *args, **kwargs):
        staff = self._current_staff()
        if staff is None:
            raise PermissionDenied("Unable to identify the requesting staff member.")

        serializer = StaffChangeRequestCreateSerializer(
            data=request.data, context={"staff": staff}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        instance = StaffChangeRequest.objects.create(
            requested_by_id=staff.staff_unique_id,
            approver_id=staff.staff_head_id,
            field_name=data["field_name"],
            old_value=data["old_value"],
            new_value=data["new_value"],
            reason=data.get("reason"),
        )

        self.log_audit(
            request,
            instance=instance,
            previous_data=None,
            new_data=self._serialize_instance(instance),
        )

        read_serializer = StaffChangeRequestSerializer(instance)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def _authorize_decision(self, request, instance):
        staff = self._current_staff()
        is_resolved_approver = (
            staff is not None and instance.approver_id == staff.staff_unique_id
        )
        if not is_resolved_approver and not getattr(request.user, "is_superuser", False):
            raise PermissionDenied("Only the assigned approver can decide this request.")
        return staff

    @action(detail=True, methods=["post"])
    def approve(self, request, unique_id=None):
        instance = self.get_object()
        if instance.status != StaffChangeRequest.Status.PENDING:
            raise ValidationError({"status": "This request has already been decided."})

        decider = self._authorize_decision(request, instance)
        serializer = StaffChangeRequestDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        previous_data = self._serialize_instance(instance)

        with transaction.atomic():
            personal_details, _ = StaffPersonalDetails.objects.get_or_create(
                staff_id=instance.requested_by_id
            )
            setattr(personal_details, instance.field_name, instance.new_value)
            personal_details.save(update_fields=[instance.field_name, "updated_at"])

            instance.status = StaffChangeRequest.Status.APPROVED
            instance.decided_by_id = getattr(decider, "staff_unique_id", None)
            instance.decided_at = timezone.now()
            instance.decision_remarks = serializer.validated_data.get("decision_remarks")
            instance.save(update_fields=[
                "status", "decided_by_id", "decided_at", "decision_remarks",
            ])

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(StaffChangeRequestSerializer(instance).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, unique_id=None):
        instance = self.get_object()
        if instance.status != StaffChangeRequest.Status.PENDING:
            raise ValidationError({"status": "This request has already been decided."})

        decider = self._authorize_decision(request, instance)
        serializer = StaffChangeRequestDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        previous_data = self._serialize_instance(instance)

        instance.status = StaffChangeRequest.Status.REJECTED
        instance.decided_by_id = getattr(decider, "staff_unique_id", None)
        instance.decided_at = timezone.now()
        instance.decision_remarks = serializer.validated_data.get("decision_remarks")
        instance.save(update_fields=["status", "decided_by_id", "decided_at", "decision_remarks"])

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(StaffChangeRequestSerializer(instance).data)
