from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.exceptions import NotAuthenticated
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet

from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.audits.staff_template_audit_log import StaffTemplateAuditLog
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.schedule_masters.alternative_staff_template_serializer import (
    AlternativeStaffTemplateSerializer
)
from app.utils.audit_mixin import AuditViewSetMixin



class AlternativeStaffTemplateViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    """
    API Contract:
    - Create alternative staff mapping
    - Approve / Reject mapping
    - Filter by status, date, template
    """

    queryset = AlternativeStaffTemplate.objects.select_related(
        "staff_template",
        "driver_id",
        "operator_id",
    )
    serializer_class = AlternativeStaffTemplateSerializer

    #  CRITICAL: single source of truth for middleware
    permission_resource = "AlternativeStaffTemplate"
    lookup_field = "unique_id"

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "alternative-staff-templates"

    def get_queryset(self):
        qs = super().get_queryset()

        staff_template = self.request.query_params.get("staff_template")
        approval_status = self.request.query_params.get("approval_status")
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")

        if staff_template:
            qs = qs.filter(staff_template_id=staff_template)

        if approval_status:
            qs = qs.filter(approval_status=approval_status)

        if from_date:
            qs = qs.filter(from_date__gte=from_date)

        if to_date:
            qs = qs.filter(to_date__lte=to_date)

        return qs.select_related(
            "staff_template",
            "driver_id",
            "operator_id",
            # "requested_by",
            "approved_by",
        )

    # --------------------------------------------------
    # ✅ USER RESOLUTION (NO SUPERADMIN CREATION)
    # --------------------------------------------------

    def _resolve_request_user(self):
        from app.models.user_creations.staffcreation import StaffcreationOfficeDetails

        # 1. Try JWT payload (BEST METHOD)
        payload = getattr(self.request, "jwt_payload", None)
        if isinstance(payload, dict):
            unique_id = payload.get("unique_id")
            if unique_id:
                staff = StaffcreationOfficeDetails.objects.filter(
                    staff_unique_id=unique_id
                ).first()
                if staff:
                    return staff

        # 2. Fallback → username match
        user = getattr(self.request, "user", None)

        if user and not getattr(user, "is_anonymous", False):
            # Try to map logged-in user to staff
            staff = Staffcreation.objects.filter(username=user.username).first()
            return staff  # may be None (allowed)

        # JWT fallback
        payload = getattr(self.request, "jwt_payload", None)
        unique_id = payload.get("unique_id") if isinstance(payload, dict) else None

        if unique_id:
            return Staffcreation.objects.filter(staff_unique_id=unique_id).first()

        return None

    def perform_create(self, serializer):
        user = self._resolve_request_user()

        instance = serializer.save(
            approval_status="PENDING",
            # requested_by=user,  # can be None if allowed in model
        )

        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=new_data
        )

        self._log_audit(
            user=user,
            action=StaffTemplateAuditLog.Action.CREATE,
            entity_id=instance.unique_id,
            remarks=instance.change_remarks,
        )

    def perform_update(self, serializer):

        if not self.request.user.is_authenticated:
            raise NotAuthenticated("Authentication required")

        staff_user = self._resolve_request_user()

        previous_data = self._serialize_instance(serializer.instance)

        instance = serializer.save()

        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=new_data
        )

        if staff_user:
            self._log_audit(
                user=staff_user,
                action=StaffTemplateAuditLog.Action.MODIFY,
                entity_id=instance.unique_id,
                remarks=instance.change_remarks,
            )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.approval_status == "APPROVED":
            return Response(
                {"detail": "Approved records cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)

    def _resolve_performed_role(self, user):
        role = getattr(getattr(user, "staffusertype_id", None), "name", "") or ""
        role = role.lower()
        if role == "admin":
            return StaffTemplateAuditLog.PerformedRole.ADMIN
        if role == "supervisor":
            return StaffTemplateAuditLog.PerformedRole.SUPERVISOR
        return StaffTemplateAuditLog.PerformedRole.SUPERVISOR

    def _log_audit(self, user, action, entity_id, remarks=None, company_id=None, project_id=None):
        if not user:
            return
        StaffTemplateAuditLog.objects.create(
            entity_type=StaffTemplateAuditLog.EntityType.ALTERNATIVE_TEMPLATE,
            entity_id=str(entity_id),
            action=action,
            performed_by=user,
            performed_role=self._resolve_performed_role(user),
            change_remarks=remarks if isinstance(remarks, str) else None,
        )
