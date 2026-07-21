
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import NotAuthenticated

from app.models.user_creations.staffcreation import Staffcreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.superadmin.audits.staff_template_audit_log import StaffTemplateAuditLog
from app.utils.base_models import Account 

from app.serializers.schedule_masters.staff_template_serializer import (
    StaffTemplateSerializer
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.roles import is_admin_role, is_super_admin


class StaffTemplateViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """
    Staff Template API
    """

    serializer_class = StaffTemplateSerializer
    lookup_field = "unique_id"
    permission_resource = "StaffTemplateCreation"

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staff-templates"

    def get_queryset(self):
        qs = StaffTemplate.objects.all()

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        approval_status = self.request.query_params.get("approval_status")
        if approval_status:
            qs = qs.filter(approval_status=approval_status)

        qs = filter_flat_geo_queryset_by_params(qs, self.request.query_params)
        qs = filter_flat_geo_queryset_by_requester_scope(qs, self.request.user)

        return qs.select_related(
            "driver_id",
            "driver_id__designation_id",
            "driver_id__corporation",
            "operator_id",
            "operator_id__designation_id",
            "operator_id__corporation",
            "created_by",
            "updated_by",
            "approved_by",
            "state",
            "district",
            "area_type",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": "Staff template deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    # ================= USER RESOLVE =================

    def _resolve_request_user(self):
        user = getattr(self.request, "user", None)

        if user and not getattr(user, "is_anonymous", False):
            if isinstance(user, Staffcreation) or hasattr(user, "staff_unique_id"):
                return user

            staff = getattr(user, "staff", None)
            if staff:
                return staff

        raw_request = getattr(self.request, "_request", None)
        raw_user = getattr(raw_request, "user", None) if raw_request else None

        if raw_user and not getattr(raw_user, "is_anonymous", False):
            if isinstance(raw_user, Staffcreation) or hasattr(raw_user, "staff_unique_id"):
                return raw_user

            staff = getattr(raw_user, "staff", None)
            if staff:
                return staff

        payload = getattr(self.request, "jwt_payload", None) or getattr(raw_request, "jwt_payload", None)
        unique_id = payload.get("unique_id") if isinstance(payload, dict) else None

        if unique_id:
            return Staffcreation.objects.filter(staff_unique_id=unique_id).first()

        return None

    # ================= ACCOUNT RESOLVE (FIX) =================


    def _get_account(self, staff_user, request_user):
        """
        Always return Account (never None)
        """

        if staff_user:
            account, _ = Account.objects.get_or_create(staff=staff_user)
            return account

        if request_user and not request_user.is_anonymous:
            account, _ = Account.objects.get_or_create(user=request_user)
            return account

        return None

    # ================= CREATE =================

    def perform_create(self, serializer):
        staff_user = self._resolve_request_user()
        request_user = getattr(self.request, "user", None)

        if not staff_user and (not request_user or request_user.is_anonymous):
            raise NotAuthenticated("Authentication required")

        account = self._get_account(staff_user, request_user)

        if not account:
            raise Exception("Account not found or created")  # 🔥 fail fast

        instance = serializer.save(
            created_by=account,
            updated_by=account,
            approved_by=serializer.validated_data.get("approved_by"),
        )

        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=new_data
        )

        if staff_user:
            self._log_audit(
                user=staff_user,
                action=StaffTemplateAuditLog.Action.CREATE,
                entity_id=instance.unique_id,
                remarks=None,
            )
    # ================= UPDATE =================

    def perform_update(self, serializer):
        staff_user = self._resolve_request_user()
        request_user = getattr(self.request, "user", None)

        if not staff_user and (not request_user or request_user.is_anonymous):
            raise NotAuthenticated("Authentication required")

        # ✅ FIX: Convert to Account
        account = self._get_account(staff_user, request_user)

        # instance = serializer.save(
        #     updated_by=account,
        #     approved_by=serializer.validated_data.get(
        #         "approved_by",
        #         serializer.instance.approved_by
        #     ),
        # )

        previous_data = self._serialize_instance(serializer.instance)

        instance = serializer.save(
            updated_by=account,
            approved_by=serializer.validated_data.get(
                "approved_by",
                serializer.instance.approved_by
            ),
        )

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
                remarks=None,
            )

    # ================= AUDIT =================

    def _resolve_performed_role(self, user):
        # Recognise admin/supervisor across all three role axes (company /
        # contractor / government) rather than only ``staffusertype_id``, so a
        # ``govt_corporation_admin`` is logged as ADMIN and a
        # ``govt_corporation_supervisor`` as SUPERVISOR.
        if is_super_admin(user) or is_admin_role(user):
            return StaffTemplateAuditLog.PerformedRole.ADMIN

        return StaffTemplateAuditLog.PerformedRole.SUPERVISOR

    def _log_audit(self, user, action, entity_id, remarks=None):
        if not user:
            return

        StaffTemplateAuditLog.objects.create(
            entity_type=StaffTemplateAuditLog.EntityType.STAFF_TEMPLATE,
            entity_id=str(entity_id),
            action=action,
            performed_by=user,
            performed_role=self._resolve_performed_role(user),
            change_remarks=remarks if isinstance(remarks, str) else None,
        )
