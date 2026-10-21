"""Driver-reported trip delays (puncture, traffic, minor repair, ...).

    POST  /api/v1/schedule-operations/trip-delay-reports/              (driver, multipart)
    GET   /api/v1/schedule-operations/trip-delay-reports/?mine=true    (supervisor)
    GET   /api/v1/schedule-operations/trip-delay-reports/{id}/
    PATCH /api/v1/schedule-operations/trip-delay-reports/{id}/acknowledge/  {supervisor_remarks?}
    PATCH /api/v1/schedule-operations/trip-delay-reports/{id}/resolve/      {supervisor_remarks?}

Deliberately thin compared with VehicleBreakdownViewSet: a delay changes
nothing about the trip, so there is no vehicle/crew reassignment here — only
create (driver), list/retrieve (supervisor) and two state nudges.
"""

from django.db.models import Q
from django.http import Http404
from rest_framework import filters, status, viewsets, mixins
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from app.utils.roles import can_manage_trips
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.core_modules.daily_operations.trip_delay_report_serializer import (
    TripDelayAcknowledgeSerializer,
    TripDelayReportSerializer,
)
from app.services.staff_notification_service import notify_staff
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.pagination import LimitOffsetWithPage
from app.utils.plain_ref import ref_q


def _truthy(value):
    return bool(value) and str(value).lower() in ("1", "true", "yes")


class TripDelayReportViewSet(AuditViewSetMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    throttle_scope = "trip_delay_report"
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = TripDelayReport.objects.filter(is_deleted=False)
    serializer_class = TripDelayReportSerializer
    lookup_field = "unique_id"
    permission_resource = "TripDelayReport"
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["created_at", "status", "delay_reason"]

    AUDIT_MODULE = "schedule-operations"
    AUDIT_ENDPOINT = "trip-delay-reports"

    # ------------------------------------------------------------------
    def _staff_uid(self):
        return getattr(getattr(self.request, "user", None), "staff_unique_id", None)

    def _owned_filter(self, staff_uid):
        """Reports the staff member owns outright: ones they reported, and
        ones on trips whose plan they supervise."""
        return Q(reported_by_id=staff_uid) | ref_q(
            "trip_assignment_id",
            DailyTripAssignment,
            trip_plan_id__in=TripPlan.objects.filter(
                supervisor_id=staff_uid
            ).values("unique_id"),
        )

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        trip_assignment = params.get("trip_assignment_id")
        if trip_assignment:
            qs = qs.filter(trip_assignment_id=trip_assignment)
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("delay_reason"):
            qs = qs.filter(delay_reason=params["delay_reason"])
        trip_date = params.get("date") or params.get("trip_date")
        if trip_date:
            qs = qs.filter(ref_q("trip_assignment_id", DailyTripAssignment, trip_date=trip_date))

        search = (params.get("search") or params.get("q") or "").strip()
        if search:
            qs = qs.filter(
                Q(unique_id__icontains=search)
                | Q(trip_assignment_id__icontains=search)
                | Q(delay_reason__icontains=search)
                | Q(delay_remarks__icontains=search)
                | Q(status__icontains=search)
                | ref_q(
                    "reported_by_id", Staffcreation, "staff_unique_id",
                    employee_name__icontains=search,
                )
                | ref_q(
                    "trip_assignment_id",
                    DailyTripAssignment,
                    vehicle_id__in=VehicleCreation.objects.filter(
                        vehicle_no__icontains=search
                    ).values("unique_id"),
                )
            )

        qs = filter_flat_geo_queryset_by_params(qs, params)

        # `mine=true` mirrors the retrip/assignment lists: the reports on
        # trips this supervisor owns (plus the ones the caller reported), with
        # no geo narrowing on top — plan ownership is itself the grant.
        if _truthy(params.get("mine")):
            staff_uid = self._staff_uid()
            return qs.filter(self._owned_filter(staff_uid)) if staff_uid else qs.none()

        return filter_flat_geo_queryset_by_requester_scope(qs, self.request.user)

    def get_object(self):
        """Fall back to ownership (reporter / plan supervisor) when the
        geo-scoped queryset does not contain the report — a supervisor opens
        a report straight from its push notification, with no `mine` flag."""
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = self.filter_queryset(self.get_queryset()).filter(**filter_kwargs).first()
        if obj is None:
            staff_uid = self._staff_uid()
            if staff_uid:
                obj = TripDelayReport.objects.filter(
                    self._owned_filter(staff_uid), is_deleted=False, **filter_kwargs
                ).first()
        if obj is None:
            raise Http404("No TripDelayReport matches the given query.")
        self.check_object_permissions(self.request, obj)
        return obj

    # ------------------------------------------------------------------
    def perform_create(self, serializer):
        """Stamp the reporter (and audit actor) server-side, then tell the
        trip's supervisor. Geography is copied from the trip by the model."""
        user = self.request.user
        reporter_id = user.staff_unique_id if isinstance(user, Staffcreation) else None
        try:
            serializer.save(
                reported_by_id=reporter_id,
                **self._audit_save_kwargs(create=True),
            )
        except Exception as exc:
            self.log_audit(
                self.request,
                instance=None,
                previous_data=None,
                new_data=None,
                success=False,
                reason=self._format_audit_error(exc),
            )
            raise
        instance = serializer.instance
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=self._serialize_instance(instance),
        )
        self._notify_supervisors(instance)

    def _notify_supervisors(self, report):
        """Best-effort: a notification failure must never lose the driver's
        report, which is already saved by the time we get here."""
        assignment = report.trip_assignment
        if assignment is None:
            return
        trip_plan = assignment.trip_plan
        plan_supervisor = getattr(trip_plan, "supervisor", None) if trip_plan else None
        recipients = [plan_supervisor] if plan_supervisor is not None else []

        minutes = report.estimated_delay_minutes
        suffix = f" (~{minutes} min)" if minutes else ""
        for staff in recipients:
            try:
                notify_staff(
                    staff,
                    StaffNotification.TYPE_TRIP_DELAY_REPORTED,
                    "Trip delayed",
                    f"{assignment.unique_id} delayed — "
                    f"{report.get_delay_reason_display()}{suffix}. "
                    f"{report.delay_remarks}",
                    data={
                        "event": "trip_delay_reported",
                        "delay_report_id": report.unique_id,
                        "assignment_id": assignment.unique_id,
                        "delay_reason": report.delay_reason,
                    },
                )
            except Exception:  # noqa: BLE001 — see docstring
                continue

    def _review(self, request, apply):
        if not can_manage_trips(request.user):
            raise PermissionDenied("Only supervisors and admins can review delays.")
        report = self.get_object()
        payload = TripDelayAcknowledgeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        previous_data = self._serialize_instance(report)
        changed = apply(report, payload.validated_data.get("supervisor_remarks"))
        if changed:
            self.log_audit(
                request,
                instance=report,
                previous_data=previous_data,
                new_data=self._serialize_instance(report),
            )
        return report, changed

    @action(detail=True, methods=["patch"], url_path="acknowledge")
    def acknowledge(self, request, unique_id=None):
        user = request.user
        report, changed = self._review(
            request,
            lambda report, remarks: report.mark_acknowledged(
                by=user if isinstance(user, Staffcreation) else None,
                remarks=remarks,
            ),
        )
        if not changed:
            return Response(
                {
                    "status": "error",
                    "message": "This delay is not awaiting acknowledgement.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["patch"], url_path="resolve")
    def resolve(self, request, unique_id=None):
        report, changed = self._review(
            request,
            lambda report, remarks: report.mark_resolved(remarks=remarks),
        )
        if not changed:
            return Response(
                {"status": "error", "message": "This delay is already resolved."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(report).data)
