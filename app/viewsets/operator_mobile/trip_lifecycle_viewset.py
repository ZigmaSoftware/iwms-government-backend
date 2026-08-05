"""Explicit trip start / end for the driver app.

Before this, a trip was started only as a *side effect* of the first bin scan
(`scan_bin_viewset._ensure_assignment_in_progress`) — so a household trip was
never started at all — and ended only if every stop happened to resolve, which
a `Skipped` / collect-later stop makes impossible. Nothing auto-closes trips,
so those sat `In Progress` forever.

    POST /api/v1/operator-mobile/trip-lifecycle/{unique_id}/start/
    POST /api/v1/operator-mobile/trip-lifecycle/{unique_id}/end/

`end` is the interesting one: with stops left it does NOT close the trip. It
raises a `TripRetripRequest` (mandatory reason) for a supervisor to decide, and
the trip stays In Progress until they do — see `app/services/retrip_service.py`.
"""

from django.utils import timezone
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.trip_today_serializer import MyTripTodaySerializer
from app.services import retrip_service
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    _effective_extra_operator_ids,
    _effective_staff_q,
    resolve_operator_staff,
)


class TripLifecycleViewSet(viewsets.ViewSet):
    """Driver-initiated start / end for one of *their own* trips today."""

    permission_classes = [IsOperatorRole]

    # ------------------------------------------------------------------
    def _resolve_own_assignment(self, request, unique_id):
        """The trip must be today's and this crew's own — by id, regardless of
        its current status.

        Deliberately does NOT reuse `find_all_active_assignments_for_operator`
        (the home-page feed): that helper drops Completed trips so a finished
        trip disappears from the driver's worklist, but start/end still need
        to resolve a Completed/Cancelled trip by id in order to return the
        accurate `ALREADY_ENDED` / `TRIP_CANCELLED` 409 below, instead of a
        generic 404 that reads like the trip was never the driver's.
        """
        operator = resolve_operator_staff(request.user)
        today = timezone.localdate()

        try:
            assignment = DailyTripAssignment.objects.get(
                unique_id=unique_id, trip_date=today, is_deleted=False,
            )
        except DailyTripAssignment.DoesNotExist:
            raise OperatorFlowError(
                "TRIP_NOT_YOURS",
                "This trip is not assigned to you today.",
                http_status=404,
            )

        is_effective_crew = DailyTripAssignment.objects.filter(
            unique_id=unique_id,
        ).filter(_effective_staff_q(operator)).exists()
        if not is_effective_crew:
            is_effective_crew = operator.staff_unique_id in (
                _effective_extra_operator_ids(assignment) or []
            )
        if not is_effective_crew:
            raise OperatorFlowError(
                "TRIP_NOT_YOURS",
                "This trip is not assigned to you today.",
                http_status=404,
            )

        return operator, assignment

    def _trip_payload(self, request, assignment):
        assignment.refresh_from_db()
        return MyTripTodaySerializer(assignment, context={"request": request}).data

    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        try:
            _, assignment = self._resolve_own_assignment(request, pk)
        except OperatorFlowError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=exc.http_status)

        if assignment.status == DailyTripAssignment.STATUS_COMPLETED:
            return Response(
                {"code": "ALREADY_ENDED", "detail": "This trip has already been completed."},
                status=http_status.HTTP_409_CONFLICT,
            )
        if assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            return Response(
                {"code": "TRIP_CANCELLED", "detail": "This trip was cancelled."},
                status=http_status.HTTP_409_CONFLICT,
            )

        # Idempotent by design: re-starting an already-running trip is a
        # success, not an error, so a flaky network can't strand the driver.
        started = assignment.mark_started()
        return Response(
            {"started": started, "trip": self._trip_payload(request, assignment)},
            status=http_status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request, pk=None):
        try:
            _, assignment = self._resolve_own_assignment(request, pk)
        except OperatorFlowError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=exc.http_status)

        operator = resolve_operator_staff(request.user)

        if assignment.status == DailyTripAssignment.STATUS_COMPLETED:
            return Response(
                {"code": "ALREADY_ENDED", "detail": "This trip has already been completed."},
                status=http_status.HTTP_409_CONFLICT,
            )
        if assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            return Response(
                {"code": "TRIP_CANCELLED", "detail": "This trip was cancelled."},
                status=http_status.HTTP_409_CONFLICT,
            )

        existing = assignment.retrip_requests.filter(
            status=TripRetripRequest.STATUS_PENDING
        ).first()
        if existing is not None:
            return Response(
                {
                    "code": "RETRIP_PENDING",
                    "detail": "A Re-Trip request for this trip is already awaiting approval.",
                    "retrip_request": _serialize_request(existing),
                },
                status=http_status.HTTP_409_CONFLICT,
            )

        pending_bins = assignment.pending_bin_stops().count()
        pending_households = assignment.pending_household_stops().count()

        # Clean finish — nothing outstanding, close it here and now.
        if not pending_bins and not pending_households:
            assignment.mark_ended()
            return Response(
                {"ended": True, "trip": self._trip_payload(request, assignment)},
                status=http_status.HTTP_200_OK,
            )

        # Stops remain → the driver must justify cutting the trip short, and a
        # supervisor decides what happens to the leftovers.
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response(
                {
                    "code": "REASON_REQUIRED",
                    "detail": "Enter a reason to request the next trip for the remaining stops.",
                    "pending_bin_count": pending_bins,
                    "pending_household_count": pending_households,
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        retrip = retrip_service.request_retrip(
            assignment, requested_by=operator, reason=reason
        )
        return Response(
            {
                "ended": False,
                "retrip_requested": True,
                "retrip_request": _serialize_request(retrip),
                "trip": self._trip_payload(request, assignment),
            },
            status=http_status.HTTP_201_CREATED,
        )


def _serialize_request(retrip):
    return {
        "unique_id": retrip.unique_id,
        "status": retrip.status,
        "reason": retrip.reason,
        "pending_bin_count": retrip.pending_bin_count,
        "pending_household_count": retrip.pending_household_count,
        "created_at": retrip.created_at.isoformat() if retrip.created_at else None,
        "reviewed_at": retrip.reviewed_at.isoformat() if retrip.reviewed_at else None,
        "review_remarks": retrip.review_remarks,
        "new_assignment_id": retrip.new_assignment_id,
    }
