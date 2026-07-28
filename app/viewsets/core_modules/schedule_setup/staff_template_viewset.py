
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotAuthenticated

from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.audits.staff_template_audit_log import StaffTemplateAuditLog
from app.utils.base_models import Account 

from app.serializers.core_modules.schedule_setup.staff_template_serializer import (
    StaffTemplateSerializer
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
    filter_staff_queryset_by_requester_scope,
)
from app.utils.roles import is_admin_role, is_super_admin
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.staff_notification_service import notify_staff


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

    # ── available-staff action ────────────────────────────────────────
    # Staff NOT already driver/operator on another ACTIVE team, so the "Add
    # team" form can't double-book someone already on a team. `exclude_id`
    # lets an edit keep showing the template's own current driver/operator.
    # role param: "driver" or "operator".

    @action(detail=False, methods=["get"], url_path="available-staff")
    def available_staff(self, request):
        role = request.query_params.get("role")
        if role not in ("driver", "operator"):
            return Response(
                {"detail": "role query param is required ('driver' or 'operator')."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exclude_id = request.query_params.get("exclude_id")

        active_templates = StaffTemplate.objects.filter(
            status=StaffTemplate.Status.ACTIVE, is_deleted=False
        )
        if exclude_id:
            active_templates = active_templates.exclude(unique_id=exclude_id)

        busy_ids = set(active_templates.values_list("driver_id", flat=True)) | set(
            active_templates.values_list("operator_id", flat=True)
        )

        # Role names vary by scope (govt_panchayat_driver, govt_district_driver,
        # ...) — match on "contains" rather than an exact/scoped name, same as
        # the frontend's own driver/operator dropdown fetch.
        qs = Staffcreation.objects.filter(
            Q(governmentusertype_id__name__icontains=role)
            | Q(staffusertype_id__name__icontains=role),
            is_deleted=False,
            active_status=True,
        ).exclude(staff_unique_id__in=busy_ids)

        qs = filter_staff_queryset_by_requester_scope(qs, request.user)

        data = [
            {
                "staff_unique_id": s.staff_unique_id,
                "employee_name": s.employee_name,
            }
            for s in qs.order_by("employee_name")
        ]
        return Response(data)

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

        self._notify_team_change(previous_data, new_data, instance)

    def _notify_team_change(self, previous_data, new_data, instance):
        """Alert whichever driver/operator was swapped on or off this team —
        both the one who lost the slot and the one who now holds it."""
        changed_staff_ids = set()
        for field in ("driver_id", "operator_id"):
            old_value = previous_data.get(field)
            new_value = new_data.get(field)
            if old_value != new_value:
                changed_staff_ids.update({old_value, new_value})
        changed_staff_ids.discard(None)
        if not changed_staff_ids:
            return

        for staff in Staffcreation.objects.filter(staff_unique_id__in=changed_staff_ids):
            notify_staff(
                staff,
                StaffNotification.TYPE_TEAM_CHANGED,
                title="Team assignment changed",
                body=f"Your team assignment ({instance.display_code}) has been updated.",
                data={"staff_template_id": instance.unique_id},
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
