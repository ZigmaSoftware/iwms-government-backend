"""Supervisor review of driver Re-Trip requests.

    GET  /api/v1/schedule-operations/retrip-requests/?status=Pending&mine=true
    POST /api/v1/schedule-operations/retrip-requests/{id}/approve/
    POST /api/v1/schedule-operations/retrip-requests/{id}/reject/

`approve` is where the continuation trip is born — see
`app/services/retrip_service.approve_retrip`. For a bin trip the supervisor
sends `collection_point_ids` (the stops they ticked); for a household trip
every remaining household carries over automatically.
"""

from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.serializers.core_modules.daily_operations.trip_retrip_serializer import (
    TripRetripRequestSerializer,
)
from app.services import retrip_service


class TripRetripRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TripRetripRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = (
            TripRetripRequest.objects.filter(is_deleted=False)
            .select_related(
                "assignment",
                "assignment__trip_plan_id",
                "assignment__vehicle_id",
                "assignment__panchayat",
                "requested_by",
                "reviewed_by",
                "new_assignment",
            )
            .order_by("-created_at")
        )

        params = self.request.query_params
        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        # `mine=true` mirrors daily_trip_assignment_viewset.py:138-141 so the
        # supervisor app sees exactly the requests for trips it owns.
        mine = params.get("mine")
        if mine and str(mine).lower() in ("1", "true", "yes"):
            staff_uid = getattr(getattr(self.request, "user", None), "staff_unique_id", None)
            qs = (
                qs.filter(assignment__trip_plan_id__supervisor_id=staff_uid)
                if staff_uid
                else qs.none()
            )

        return qs

    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, unique_id=None):
        retrip = self.get_object()
        if not retrip.is_pending:
            return Response(
                {"detail": f"This request was already {retrip.status.lower()}."},
                status=http_status.HTTP_409_CONFLICT,
            )

        raw_ids = request.data.get("collection_point_ids")
        collection_point_ids = None
        if raw_ids is not None:
            if not isinstance(raw_ids, (list, tuple)):
                return Response(
                    {"collection_point_ids": "Expected a list of stop ids."},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )
            collection_point_ids = [str(value) for value in raw_ids]

        reviewer = getattr(request, "user", None)
        continuation = retrip_service.approve_retrip(
            retrip,
            reviewed_by=reviewer if _is_staff_record(reviewer) else None,
            collection_point_ids=collection_point_ids,
            remarks=request.data.get("remarks"),
        )

        retrip.refresh_from_db()
        return Response(
            {
                "request": TripRetripRequestSerializer(retrip, context={"request": request}).data,
                "new_assignment_id": continuation.unique_id,
            },
            status=http_status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, unique_id=None):
        retrip = self.get_object()
        if not retrip.is_pending:
            return Response(
                {"detail": f"This request was already {retrip.status.lower()}."},
                status=http_status.HTTP_409_CONFLICT,
            )

        reviewer = getattr(request, "user", None)
        retrip_service.reject_retrip(
            retrip,
            reviewed_by=reviewer if _is_staff_record(reviewer) else None,
            remarks=request.data.get("remarks"),
        )

        retrip.refresh_from_db()
        return Response(
            TripRetripRequestSerializer(retrip, context={"request": request}).data,
            status=http_status.HTTP_200_OK,
        )


def _is_staff_record(user):
    """`reviewed_by` is a Staffcreation FK; an Account login is not one."""
    from app.models.superadmin.staff_management.staffcreation import Staffcreation

    return isinstance(user, Staffcreation)
