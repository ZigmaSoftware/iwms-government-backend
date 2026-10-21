from datetime import datetime, time as datetime_time, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.utils.plain_ref import json_contains_any, ref_q
from app.utils.plain_ref_search import PlainRefSearchFilter
from app.management.commands.generate_daily_trips import run_for_date
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.scheduler_config import SchedulerConfig
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.core_modules.daily_operations.daily_service_notice import DailyServiceNotice
from app.services.daily_service_notice import (active_notice_for_plan, serialize_notice, declare_no_collection, revoke_no_collection, DailyServiceNoticeError)
from app.services.daily_trip_generation import generate_assignment_for_plan
from app.services import retrip_service
from app.services.daily_trip_scheduler import (
    run_daily_trip_job,
    scheduler_status as get_scheduler_status,
)
from app.serializers.core_modules.daily_operations.daily_trip_assignment_serializer import (
    DailyTripAssignmentSerializer,
    DailyTripAssignmentStatusSerializer,
    DailyTripAssignmentApprovalSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import (
    flat_geo_display,
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.pagination import LimitOffsetWithPage
from app.utils.roles import can_manage_trips, is_supervisor_role
from rest_framework import viewsets
from app.utils.bulk_upload_mixin import BulkUploadMixin


class DailyTripAssignmentViewSet(BulkUploadMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD + state-machine actions for daily trip assignments.

    Custom actions:
      PATCH  /{unique_id}/status/    — state machine transition
      PATCH  /{unique_id}/approval/  — approval flow (supervisor/admin only)
    """
    throttle_scope = "daily_trip_assignment"

    queryset = DailyTripAssignment.objects.filter(is_deleted=False)

    serializer_class = DailyTripAssignmentSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripAssignment"
    # Supervisor-app day planning. Each action enforces its own gate —
    # supervisor/admin role (`_has_approval_role`) AND only plans the caller
    # supervises (or, for admins, their geo scope) via `_owned_plans` — so
    # the generic screen grant ("add" on daily-trip-plan, which supervisors'
    # role template does not carry) must not block them.
    permission_exempt_actions = (
        "today_plan_options",
        "generate_selected",
        "no_collection",
        "revoke_service_notice",
    )
    filter_backends = [PlainRefSearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "unique_id",
        "status",
        "approval_status",
        "vehicle_id=app.models.masters.transport_masters.vehicleCreation.VehicleCreation.vehicle_no",
        "trip_plan_id=app.models.core_modules.schedule_setup.trip_plan.TripPlan.display_code",
        "trip_plan_id=app.models.core_modules.schedule_setup.trip_plan.TripPlan.collection_type",
        "staff_template_id=app.models.core_modules.schedule_setup.staff_template.StaffTemplate.display_code",
        "staff_template_id=app.models.core_modules.schedule_setup.staff_template.StaffTemplate.driver_id"
        "=app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails.employee_name",
        "staff_template_id=app.models.core_modules.schedule_setup.staff_template.StaffTemplate.operator_id"
        "=app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails.employee_name",
        "state_id=app.models.superadmin.common_masters.state.State.name",
        "district_id=app.models.masters.district.District.name",
        "corporation_id=app.models.masters.corporation.Corporation.corporation_name",
        "municipality_id=app.models.masters.municipality.Municipality.municipality_name",
        "town_panchayat_id=app.models.masters.town_panchayat.TownPanchayat.town_panchayat_name",
        "panchayat_union_id=app.models.masters.panchayat_union.PanchayatUnion.union_name",
        "panchayat_id=app.models.masters.panchayat.Panchayat.panchayat_name",
        "ward_ids[]=app.models.masters.ward.Ward.ward_name",
    ]
    ordering_fields = ["trip_date", "scheduled_time", "status", "approval_status"]

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
        waste_type = params.get("waste_type_id") or params.get("waste_type_ids")
        ward_id = params.get("ward_id") or params.get("ward_ids")

        if trip_date:
            qs = qs.filter(trip_date=trip_date)

        if today_flag and str(today_flag).lower() in ("1", "true", "yes"):
            qs = qs.filter(trip_date=timezone.localdate())

        if trip_plan:
            qs = qs.filter(trip_plan_id=trip_plan)

        if trip_status:
            qs = qs.filter(status=trip_status)

        if waste_type:
            qs = qs.filter(json_contains_any("waste_type_ids", [waste_type]))
        if ward_id:
            qs = qs.filter(json_contains_any("ward_ids", [ward_id]))

        qs = filter_flat_geo_queryset_by_params(qs, params)

        # `mine=true` → only trips this supervisor is responsible for
        # (TripPlan.supervisor_id == the requesting staff). Used by the
        # supervisor mobile app to list the trips it owns.
        #
        # Being named supervisor on a trip plan is an explicit, per-plan
        # grant, and supervisors are routinely given plans outside their own
        # geo branch (a panchayat supervisor scoped to a corporation, say).
        # ANDing that grant with the geo scope silently returned nothing in
        # exactly that case, so an assigned supervisor saw an empty trip list
        # — and with it empty Trips/Vehicles/Teams counts. The filter matches
        # only the requester's own staff id, so it is self-scoping already and
        # needs no geo narrowing on top.
        mine = params.get("mine")
        if mine and str(mine).lower() in ("1", "true", "yes"):
            staff_uid = getattr(getattr(self.request, "user", None), "staff_unique_id", None)
            if not staff_uid:
                return qs.none()
            return qs.filter(ref_q("trip_plan_id", TripPlan, supervisor_id=staff_uid))

        return filter_flat_geo_queryset_by_requester_scope(qs, self.request.user)

    def get_object(self):
        """
        Detail-level access (retrieve/update/destroy, and the `status`/
        `approval` actions below) must not depend on the caller remembering
        to pass `?mine=true` the way the list endpoint does. Being named
        supervisor on a trip's plan is an explicit, standing grant — the
        supervisor app substitutes staff, starts/ends trips, and approves
        stops on assignments it owns via a single-object PATCH, with no
        listing step in between where a `mine` flag would even apply. A
        supervisor whose broader geo scope doesn't cover this one trip
        would otherwise get a 404 on every one of those actions despite
        genuinely owning the trip. Fall back to trip-plan ownership whenever
        the default (geo-scoped) queryset doesn't contain the object; this
        only ever widens access to trips the requester was explicitly
        assigned, never sideways to unrelated ones.
        """
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}

        obj = queryset.filter(**filter_kwargs).first()
        if obj is None:
            staff_uid = getattr(getattr(self.request, "user", None), "staff_unique_id", None)
            if staff_uid:
                obj = DailyTripAssignment.objects.filter(
                    ref_q("trip_plan_id", TripPlan, supervisor_id=staff_uid),
                    is_deleted=False,
                    **filter_kwargs,
                ).first()

        if obj is None:
            from django.http import Http404

            raise Http404("No DailyTripAssignment matches the given query.")

        self.check_object_permissions(self.request, obj)
        return obj

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
        account = self._account_for_request_user()
        update_fields = ["is_deleted", "is_active", "status", "updated_at"]
        if account is not None:
            instance.updated_by = account.pk
            update_fields.append("updated_by")
        instance.save(update_fields=update_fields)

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

        # Route the two lifecycle transitions through the model so the admin
        # path stamps the same columns, in the same timezone, as the driver app
        # and the scan path. This previously wrote `timezone.now().time()` —
        # UTC — into a column every other caller filled with IST.
        if new_status == DailyTripAssignment.STATUS_IN_PROGRESS:
            instance.mark_started()
        elif new_status == DailyTripAssignment.STATUS_COMPLETED:
            instance.mark_ended()
        else:
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
    # ACTION: PROCEED WITH NEXT TRIP (web Re-Trip, one step)
    # POST /trip-assignments/{unique_id}/proceed-next-trip/
    # body: { collection_point_ids?: string[], remarks: string }
    # ----------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="proceed-next-trip")
    def proceed_next_trip(self, request, unique_id=None):
        """Supervisor/admin closes this trip from the web and opens a
        continuation for the leftover stops — e.g. the truck is full and
        going for weighment. One-step web equivalent of the driver-raises /
        supervisor-approves Re-Trip flow (see
        retrip_service.proceed_to_next_trip).
        """
        if not self._has_approval_role(request):
            return Response(
                {"detail": "Only supervisors and admins can proceed to a next trip."},
                status=status.HTTP_403_FORBIDDEN,
            )

        instance = self.get_object()

        remarks = (request.data.get("remarks") or "").strip()
        if not remarks:
            return Response(
                {"remarks": "Remarks are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_ids = request.data.get("collection_point_ids")
        collection_point_ids = None
        if raw_ids is not None:
            if not isinstance(raw_ids, (list, tuple)):
                return Response(
                    {"collection_point_ids": "Expected a list of stop ids."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            collection_point_ids = [str(value) for value in raw_ids]

        # A trip is either a bin trip or a household trip (never both) — the
        # presence of any CP rows is how the rest of the codebase tells them
        # apart (e.g. DailyTripLogReportPage's `isHousehold` check). Bin trips
        # require an explicit pick; household trips always carry everything.
        is_bin_trip = instance.trip_collection_points.exists()
        if is_bin_trip and not collection_point_ids:
            return Response(
                {"collection_point_ids": "Select at least one collection point to carry over."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actor = request.user if isinstance(request.user, Staffcreation) else None

        try:
            retrip_request, continuation = retrip_service.proceed_to_next_trip(
                instance,
                actor=actor,
                collection_point_ids=collection_point_ids,
                remarks=remarks,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "new_assignment_id": continuation.unique_id,
                "retrip_request_id": retrip_request.unique_id,
            },
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
        if is_supervisor_role(request.user):
            return Response({"detail": "Use generate-selected for your own Trip Plans."}, status=status.HTTP_400_BAD_REQUEST)
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

        if is_supervisor_role(request.user):
            return Response({"detail": "Use generate-selected for your own Trip Plans."}, status=status.HTTP_400_BAD_REQUEST)
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

    def _service_date(self, raw_date):
        if not raw_date:
            return timezone.localdate()
        try:
            return timezone.datetime.strptime(str(raw_date), "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"date": "Use YYYY-MM-DD."})

    def _owned_plans(self, ids=None):
        plans = TripPlan.objects.filter(is_deleted=False)
        if is_supervisor_role(self.request.user):
            plans = plans.filter(supervisor_id=self.request.user.staff_unique_id)
        else:
            plans = filter_flat_geo_queryset_by_requester_scope(plans, self.request.user)
        if ids is not None:
            plans = plans.filter(unique_id__in=ids)
        return plans

    def _team_members(self, template):
        """Driver, operator and extra operators of the plan's team with their
        photos, for the avatar stack on the supervisor app's plan card."""
        if template is None:
            return []
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        from app.utils.crew import crew_payload

        crew = crew_payload(template, None, timezone.localdate(), request=self.request)
        return [member for member in [crew["driver"], crew["operator"], *crew["extra_operators"]] if member]

    def _plan_option(self, plan, service_date):
        assignments = DailyTripAssignment.objects.filter(
            trip_plan_id=plan.unique_id,
            trip_date=service_date,
            is_deleted=False,
        ).order_by("created_at")
        notice = active_notice_for_plan(plan.unique_id, service_date)
        repeat_days = plan.repeat_days or []
        scheduled_today = not repeat_days or service_date.weekday() in {
            int(value) for value in repeat_days if str(value).isdigit()
        }
        blocking_reason = None
        state = "NEEDS_ASSIGNMENT"
        # A plan can hold several trips today (a cancelled run, a Re-Trip
        # continuation). Report the one that is live, not simply the oldest
        # row, so the supervisor's card follows the trip being collected.
        rank = {
            DailyTripAssignment.STATUS_IN_PROGRESS: 0,
            DailyTripAssignment.STATUS_SCHEDULED: 1,
            DailyTripAssignment.STATUS_COMPLETED: 2,
        }
        assignment = min(
            assignments,
            key=lambda a: (rank.get(a.status, 3), -a.created_at.timestamp()),
            default=None,
        )
        if notice:
            state = "NO_COLLECTION"
        elif assignment:
            state = assignment.status
        elif plan.status != TripPlan.Status.ACTIVE:
            state, blocking_reason = "BLOCKED", "Trip Plan is inactive"
        elif plan.approval_status != TripPlan.ApprovalStatus.APPROVED:
            state, blocking_reason = "BLOCKED", "Trip Plan is awaiting approval"
        elif not scheduled_today:
            state, blocking_reason = "NOT_SCHEDULED", "Trip Plan does not run today"
        elif not plan.staff_template_id:
            state, blocking_reason = "BLOCKED", "Assign a team before creating this trip"
        elif not plan.vehicle_id:
            state, blocking_reason = "BLOCKED", "Assign a vehicle before creating this trip"

        template = plan.staff_template
        vehicle = plan.vehicle
        return {
            "trip_plan_id": plan.unique_id,
            "display_code": plan.display_code,
            "collection_type": plan.collection_type,
            "scheduled_time": plan.scheduled_time.strftime("%H:%M") if plan.scheduled_time else None,
            "state": state,
            "blocking_reason": blocking_reason,
            "assignment_id": getattr(assignment, "unique_id", None),
            "assignment_status": getattr(assignment, "status", None),
            "vehicle_no": getattr(vehicle, "vehicle_no", None),
            "team_code": getattr(template, "display_code", None),
            "driver_name": getattr(getattr(template, "driver", None), "employee_name", None),
            "operator_name": getattr(getattr(template, "operator", None), "employee_name", None),
            "team_members": self._team_members(template),
            # Government geography in place of private's zone name: the
            # plan's most specific local body (falls back to district/state).
            "local_body_name": flat_geo_display(plan)[0],
            "ward_names": [getattr(ward, "ward_name", str(ward)) for ward in plan.wards.all()],
            "notice": serialize_notice(notice),
        }

    @action(detail=False, methods=["get"], url_path="today-plan-options")
    def today_plan_options(self, request):
        if not self._has_approval_role(request):
            return Response({"detail": "Supervisor access is required."}, status=status.HTTP_403_FORBIDDEN)
        service_date = self._service_date(request.query_params.get("date"))
        plans = self._owned_plans().order_by("scheduled_time", "display_code")
        options = [
            option
            for plan in plans
            if (option := self._plan_option(plan, service_date))["state"]
            != "NOT_SCHEDULED"
        ]
        return Response({
            "service_date": service_date.isoformat(),
            "results": options,
            "summary": {
                "total": len(options),
                "needs_assignment": sum(item["state"] == "NEEDS_ASSIGNMENT" for item in options),
                "assigned": sum(item["state"] in {"Scheduled", "In Progress", "Completed"} for item in options),
                "no_collection": sum(item["state"] == "NO_COLLECTION" for item in options),
                "blocked": sum(item["state"] in {"BLOCKED", "NOT_SCHEDULED"} for item in options),
            },
        })

    @action(detail=False, methods=["post"], url_path="generate-selected")
    def generate_selected(self, request):
        if not self._has_approval_role(request):
            return Response({"detail": "Supervisor access is required."}, status=status.HTTP_403_FORBIDDEN)
        service_date = self._service_date(request.data.get("date"))
        if is_supervisor_role(self.request.user) and service_date != timezone.localdate():
            return Response({"detail": "Supervisors can assign trips for today only."}, status=status.HTTP_400_BAD_REQUEST)
        raw_ids = request.data.get("trip_plan_ids")
        if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 50:
            return Response({"trip_plan_ids": "Choose between 1 and 50 Trip Plans."}, status=status.HTTP_400_BAD_REQUEST)
        ids = list(dict.fromkeys(str(value) for value in raw_ids))
        plans = list(self._owned_plans(ids))
        if len(plans) != len(ids):
            return Response({"detail": "One or more Trip Plans are unavailable or outside your responsibility."}, status=status.HTTP_403_FORBIDDEN)

        created = []
        existing = []
        blocked = []
        with transaction.atomic():
            for plan in plans:
                # Serialize simultaneous mobile taps for the same plan. The
                # assignment table deliberately permits multiple same-day
                # rows for Re-Trips, so its database schema cannot provide
                # ordinary generation with a unique constraint.
                plan = TripPlan.objects.select_for_update().get(
                    unique_id=plan.unique_id
                )
                reason = None
                if plan.status != TripPlan.Status.ACTIVE:
                    reason = "Trip Plan is inactive"
                elif plan.approval_status != TripPlan.ApprovalStatus.APPROVED:
                    reason = "Trip Plan is not approved"
                elif not plan.staff_template_id or not plan.vehicle_id:
                    reason = "A team and vehicle are required"
                elif active_notice_for_plan(plan.unique_id, service_date):
                    reason = "No collection has been declared for this date"
                repeat_days = plan.repeat_days or []
                if not reason and repeat_days and service_date.weekday() not in {int(value) for value in repeat_days if str(value).isdigit()}:
                    reason = "Trip Plan is not scheduled for this weekday"
                if reason:
                    blocked.append({"trip_plan_id": plan.unique_id, "reason": reason})
                    continue
                assignment, was_created, _ = generate_assignment_for_plan(
                    plan, service_date, created_by=self._account_for_request_user()
                )
                (created if was_created else existing).append(assignment.unique_id)
        return Response({
            "service_date": service_date.isoformat(),
            "created": created,
            "existing": existing,
            "blocked": blocked,
        })

    @action(detail=False, methods=["post"], url_path="no-collection")
    def no_collection(self, request):
        if not self._has_approval_role(request):
            return Response({"detail": "Supervisor access is required."}, status=status.HTTP_403_FORBIDDEN)
        service_date = self._service_date(request.data.get("date"))
        if is_supervisor_role(self.request.user) and service_date != timezone.localdate():
            return Response({"detail": "Supervisors can change today's service only."}, status=status.HTTP_400_BAD_REQUEST)
        raw_ids = request.data.get("trip_plan_ids")
        if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 50:
            return Response({"trip_plan_ids": "Choose between 1 and 50 Trip Plans."}, status=status.HTTP_400_BAD_REQUEST)
        ids = list(dict.fromkeys(str(value) for value in raw_ids))
        plans = list(self._owned_plans(ids))
        if len(plans) != len(ids):
            return Response({"detail": "One or more Trip Plans are outside your responsibility."}, status=status.HTTP_403_FORBIDDEN)
        account = self._account_for_request_user()
        try:
            with transaction.atomic():
                notices = [
                    declare_no_collection(
                        plan,
                        service_date,
                        str(request.data.get("reason_code") or ""),
                        str(request.data.get("reason_text") or ""),
                        actor_id=getattr(account, "pk", None),
                    )
                    for plan in plans
                ]
        except DailyServiceNoticeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        for notice in notices:
            self.log_audit(request, instance=notice, new_data=self._serialize_instance(notice))
        return Response({"results": [serialize_notice(notice) for notice in notices]}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="revoke-no-collection")
    def revoke_service_notice(self, request):
        if not self._has_approval_role(request):
            return Response({"detail": "Supervisor access is required."}, status=status.HTTP_403_FORBIDDEN)
        notice = DailyServiceNotice.objects.filter(
            unique_id=request.data.get("notice_id"), is_deleted=False
        ).first()
        if not notice or not self._owned_plans([notice.trip_plan_id]).exists():
            return Response({"detail": "Service notice not found."}, status=status.HTTP_404_NOT_FOUND)
        if is_supervisor_role(request.user) and notice.service_date != timezone.localdate():
            return Response({"detail": "Supervisors can change today's service only."}, status=status.HTTP_400_BAD_REQUEST)
        previous_data = self._serialize_instance(notice)
        account = self._account_for_request_user()
        try:
            notice = revoke_no_collection(notice, getattr(account, "pk", None), request.data.get("reason"))
        except DailyServiceNoticeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        self.log_audit(request, instance=notice, previous_data=previous_data, new_data=self._serialize_instance(notice))
        return Response({"notice": serialize_notice(notice)})

    def _has_approval_role(self, request) -> bool:
        """Returns True if the requesting user holds supervisor or admin role.

        Recognises the role across all three role axes (company / contractor /
        government), so a ``govt_corporation_admin`` or
        ``govt_corporation_supervisor`` gets approval rights the same way a
        ``company_admin`` / ``company_supervisor`` does. Platform superadmin
        always qualifies.
        """
        return can_manage_trips(getattr(request, "user", None))

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
