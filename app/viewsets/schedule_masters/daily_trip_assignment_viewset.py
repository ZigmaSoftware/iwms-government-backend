from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.serializers.schedule_masters.daily_trip_assignment_serializer import (
    DailyTripAssignmentSerializer,
    DailyTripAssignmentStatusSerializer,
    DailyTripAssignmentApprovalSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_queryset_by_hierarchy
from rest_framework import viewsets


class DailyTripAssignmentViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD + state-machine actions for daily trip assignments.

    Custom actions:
      PATCH  /{unique_id}/status/    — state machine transition
      PATCH  /{unique_id}/approval/  — approval flow (supervisor/admin only)
    """

    queryset = DailyTripAssignment.objects.select_related(
        "trip_plan_id",
        "trip_plan_id__panchayat_id",
        "trip_plan_id__corporation_id",
        "trip_plan_id__municipality_id",
        "trip_plan_id__town_panchayat_id",
        "trip_plan_id__panchayat_union_id",
        "trip_plan_id__vehicle_id",
        "trip_plan_id__waste_type_id",
        "staff_template_id",
        "staff_template_id__driver_id",
        "staff_template_id__operator_id",
        "alt_staff_template_id",
        "alt_staff_template_id__driver_id",
        "alt_staff_template_id__operator_id",
        "corporation_id",
        "municipality_id",
        "town_panchayat_id",
        "panchayat_union_id",
        "panchayat_id",
        "waste_type_id",
        "vehicle_id",
    ).filter(is_deleted=False)

    serializer_class = DailyTripAssignmentSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripAssignment"

    AUDIT_MODULE = "trip-assignments"
    AUDIT_ENDPOINT = "daily-trip-assignments"

    # ----------------------------------------------------------
    # QUERYSET FILTERS
    # ----------------------------------------------------------

    def get_queryset(self):
        qs = super().get_queryset()

        params = self.request.query_params
        trip_date = params.get("date") or params.get("trip_date")
        today_flag = params.get("today")
        trip_plan = params.get("trip_plan_id")
        trip_status = params.get("status")
        waste_type = params.get("waste_type_id")

        if trip_date:
            qs = qs.filter(trip_date=trip_date)

        if today_flag and str(today_flag).lower() in ("1", "true", "yes"):
            qs = qs.filter(trip_date=timezone.localdate())

        if trip_plan:
            qs = qs.filter(trip_plan_id=trip_plan)

        if trip_status:
            qs = qs.filter(status=trip_status)

        if waste_type:
            qs = qs.filter(waste_type_id=waste_type)

        return filter_queryset_by_hierarchy(qs, params)

    # ----------------------------------------------------------
    # UPDATE — only allowed when Scheduled
    # ----------------------------------------------------------

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.status != DailyTripAssignment.STATUS_SCHEDULED:
            return Response(
                {"detail": "Only Scheduled assignments can be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)

    # ----------------------------------------------------------
    # DELETE — soft-delete + cancel
    # ----------------------------------------------------------

    def perform_destroy(self, instance):
        previous_data = self._serialize_instance(instance)

        instance.is_deleted = True
        instance.is_active = False
        instance.status = DailyTripAssignment.STATUS_CANCELLED
        instance.save(update_fields=["is_deleted", "is_active", "status", "updated_at"])

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

    # ----------------------------------------------------------
    # ACTION: STATUS TRANSITION
    # PATCH /trip-assignments/{unique_id}/status/
    # ----------------------------------------------------------

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, unique_id=None):
        instance = self.get_object()

        serializer = DailyTripAssignmentStatusSerializer(
            data=request.data,
            context={"instance": instance, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]
        previous_data = self._serialize_instance(instance)

        now = timezone.now().time()

        if new_status == DailyTripAssignment.STATUS_IN_PROGRESS:
            instance.actual_start_time = now
        elif new_status == DailyTripAssignment.STATUS_COMPLETED:
            instance.actual_end_time = now

        instance.status = new_status
        instance.save()

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            DailyTripAssignmentSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # ACTION: APPROVAL TRANSITION
    # PATCH /trip-assignments/{unique_id}/approval/
    # ----------------------------------------------------------

    @action(detail=True, methods=["patch"], url_path="approval")
    def update_approval(self, request, unique_id=None):
        instance = self.get_object()

        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can approve or reject assignments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DailyTripAssignmentApprovalSerializer(
            data=request.data,
            context={"instance": instance, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        previous_data = self._serialize_instance(instance)
        instance.approval_status = serializer.validated_data["approval_status"]
        instance.save(update_fields=["approval_status", "updated_at"])

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            DailyTripAssignmentSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _has_approval_role(self, request) -> bool:
        """Returns True if the requesting user holds supervisor or admin role."""
        user = getattr(request, "user", None)
        if not user:
            return False

        # Platform superadmin always has approval rights
        if getattr(user, "is_superuser", False):
            return True

        role_obj = getattr(user, "staffusertype_id", None)
        role_name = getattr(role_obj, "name", "") or ""
        return role_name.lower() in ("supervisor", "admin", "company_admin")

    def perform_create(self, serializer):
        previous_data = None
        super().perform_create(serializer)
        instance = serializer.instance
        new_data = self._serialize_instance(instance)
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=new_data,
        )

    def perform_update(self, serializer):
        previous_data = self._serialize_instance(serializer.instance)
        super().perform_update(serializer)
        instance = serializer.instance
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
