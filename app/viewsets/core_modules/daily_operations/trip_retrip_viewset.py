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

from django.db.models import Q
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.plain_ref import ref_q
from app.utils.hierarchy import FLAT_GEO_QUERY_FIELDS, filter_flat_geo_queryset_by_params
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.serializers.core_modules.daily_operations.trip_retrip_serializer import (
    TripRetripRequestSerializer,
)
from app.services import retrip_service


class TripRetripRequestViewSet(viewsets.ReadOnlyModelViewSet):
    throttle_scope = "trip_retrip_request"
    serializer_class = TripRetripRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "unique_id"

    def get_queryset(self):
        qs = (
            TripRetripRequest.objects.filter(is_deleted=False)
            .order_by("-created_at")
        )

        params = self.request.query_params
        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        # The list's search box matches what the table shows: request/trip
        # ids, reason, status, requester name and vehicle number. `status`
        # also has a dedicated filter-chip; matching its text here keeps the
        # search box consistent when the panel is set to All.
        search = (params.get("search") or params.get("q") or "").strip()
        if search:
            vehicle_ids = VehicleCreation.objects.filter(
                vehicle_no__icontains=search
            ).values("unique_id")
            assignment_ids = DailyTripAssignment.objects.filter(
                Q(unique_id__icontains=search) | Q(vehicle_id__in=vehicle_ids)
            ).values("unique_id")
            qs = qs.filter(
                Q(unique_id__icontains=search)
                | Q(assignment_id__icontains=search)
                | Q(assignment_id__in=assignment_ids)
                | Q(reason__icontains=search)
                | Q(status__icontains=search)
                | ref_q(
                    "requested_by_id",
                    Staffcreation,
                    "staff_unique_id",
                    employee_name__icontains=search,
                )
            )

        # Location filter: the request carries no geo columns of its own — its
        # trip (DailyTripAssignment) does.
        if any(params.get(field) for field in FLAT_GEO_QUERY_FIELDS):
            qs = qs.filter(
                assignment_id__in=filter_flat_geo_queryset_by_params(
                    DailyTripAssignment.objects.all(), params
                ).values("unique_id")
            )

        # `mine=true` mirrors daily_trip_assignment_viewset.py:138-141 so the
        # supervisor app sees exactly the requests for trips it owns.
        mine = params.get("mine")
        if mine and str(mine).lower() in ("1", "true", "yes"):
            staff_uid = getattr(getattr(self.request, "user", None), "staff_unique_id", None)
            qs = (
                qs.filter(
                    ref_q(
                        "assignment_id",
                        DailyTripAssignment,
                        trip_plan_id__in=TripPlan.objects.filter(
                            supervisor_id=staff_uid
                        ).values("unique_id"),
                    )
                )
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
    """`reviewed_by_id` holds a Staffcreation id; an Account login is not one."""
    from app.models.superadmin.staff_management.staffcreation import Staffcreation

    return isinstance(user, Staffcreation)
