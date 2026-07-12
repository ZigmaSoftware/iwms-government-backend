from datetime import datetime, time as datetime_time, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.management.commands.generate_daily_trips import run_for_date
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.scheduler_config import SchedulerConfig
from app.services.daily_trip_scheduler import (
    notify_scheduler_config_changed,
    run_daily_trip_job,
    scheduler_status as get_scheduler_status,
)
from app.serializers.schedule_masters.daily_trip_assignment_serializer import (
    DailyTripAssignmentSerializer,
    DailyTripAssignmentStatusSerializer,
    DailyTripAssignmentApprovalSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
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
        "trip_plan_id__district",
        "trip_plan_id__panchayat",
        "trip_plan_id__corporation",
        "trip_plan_id__municipality",
        "trip_plan_id__town_panchayat",
        "trip_plan_id__panchayat_union",
        "trip_plan_id__vehicle_id",
        "trip_plan_id__waste_type_id",
        "staff_template_id",
        "staff_template_id__driver_id",
        "staff_template_id__operator_id",
        "alt_staff_template_id",
        "alt_staff_template_id__driver_id",
        "alt_staff_template_id__operator_id",
        "state",
        "district",
        "area_type",
        "corporation",
        "municipality",
        "town_panchayat",
        "panchayat_union",
        "panchayat",
        "waste_type_id",
        "vehicle_id",
    ).filter(is_deleted=False)

    serializer_class = DailyTripAssignmentSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripAssignment"

    AUDIT_MODULE = "trip-assignments"
    AUDIT_ENDPOINT = "daily-trip-assignments"

    def _scheduler_config_payload(self, config):
        now = timezone.localtime()
        run_at_today = datetime.combine(now.date(), config.run_time, tzinfo=now.tzinfo)
        next_run = run_at_today if run_at_today > now else run_at_today + timedelta(days=1)
        return {
            "run_time": config.run_time.strftime("%H:%M"),
            "is_enabled": config.is_enabled,
            "next_run_at": next_run.isoformat() if config.is_enabled else None,
        }

    def _parse_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        if value in {0, 1}:
            return bool(value)
        return None

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

        for field in ("state_id", "district_id", "area_type_id", "corporation_id", "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id"):
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})

        # `mine=true` → only trips this supervisor is responsible for
        # (TripPlan.supervisor_id == the requesting staff). Used by the
        # supervisor mobile app to list the trips it owns.
        mine = params.get("mine")
        if mine and str(mine).lower() in ("1", "true", "yes"):
            staff_uid = getattr(getattr(self.request, "user", None), "staff_unique_id", None)
            qs = qs.filter(trip_plan_id__supervisor_id=staff_uid) if staff_uid else qs.none()

        return qs

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
    # ACTIONS: BACKGROUND SCHEDULER STATUS / CONFIG / MANUAL RUN
    # GET        /daily-trip-assignments/scheduler-status/
    # GET|PATCH  /daily-trip-assignments/scheduler-config/
    # POST       /daily-trip-assignments/run-scheduler/
    # ----------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="scheduler-status")
    def scheduler_status(self, request):
        data = get_scheduler_status()
        config = SchedulerConfig.get_singleton()
        data.update(self._scheduler_config_payload(config))
        data["enabled"] = config.is_enabled
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get", "patch"], url_path="scheduler-config")
    def scheduler_config(self, request):
        config = SchedulerConfig.get_singleton()
        if request.method == "GET":
            return Response(
                self._scheduler_config_payload(config),
                status=status.HTTP_200_OK,
            )
        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can change the scheduler config."},
                status=status.HTTP_403_FORBIDDEN,
            )
        run_time_str = request.data.get("run_time")
        is_enabled = request.data.get("is_enabled")
        if run_time_str is not None:
            try:
                hour, minute = str(run_time_str).split(":", 1)
                parsed_hour = int(hour)
                parsed_minute = int(minute)
                if not (0 <= parsed_hour <= 23 and 0 <= parsed_minute <= 59):
                    raise ValueError
                config.run_time = datetime_time(parsed_hour, parsed_minute)
            except (ValueError, TypeError):
                return Response(
                    {"run_time": "Use HH:MM 24-hour format (e.g. 00:00, 04:00, 12:30)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if is_enabled is not None:
            parsed_enabled = self._parse_bool(is_enabled)
            if parsed_enabled is None:
                return Response(
                    {"is_enabled": "Use true or false."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            config.is_enabled = parsed_enabled
        config.save()
        notify_scheduler_config_changed()
        return Response(
            self._scheduler_config_payload(config),
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="run-scheduler")
    def run_scheduler(self, request):
        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can run the daily scheduler."},
                status=status.HTTP_403_FORBIDDEN,
            )
        raw_date = request.data.get("date")
        target_date = None
        if raw_date:
            try:
                target_date = timezone.datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"date": "Use YYYY-MM-DD format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        result = run_daily_trip_job(target_date=target_date, force=True)
        return Response(result, status=status.HTTP_200_OK)

    # ----------------------------------------------------------
    # ACTION: MANUAL JOB-SCHEDULER RUN  (for testing / on-demand)
    # POST /daily-trip-assignments/generate-daily/
    # body: { "date": "YYYY-MM-DD" }   (optional, defaults to today)
    # ----------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="generate-daily")
    def generate_daily(self, request):
        """Manually run the daily trip job scheduler for one date.

        Mirrors the nightly cron (`manage.py generate_daily_trips`) so admins
        can generate / back-fill a day's trips on demand without shell access.
        Idempotent — re-running the same date creates no duplicates.
        """
        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can run the daily scheduler."},
                status=status.HTTP_403_FORBIDDEN,
            )

        target_date = None
        raw_date = request.data.get("date")
        if raw_date:
            try:
                target_date = timezone.datetime.strptime(str(raw_date), "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        summary = run_for_date(target_date=target_date)

        return Response(
            {
                "message": (
                    f"Generated {summary['created']} assignment(s); "
                    f"skipped {summary['skipped']} plan(s) for {summary['date']}."
                ),
                **summary,
            },
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
