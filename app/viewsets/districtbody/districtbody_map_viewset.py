"""
District Leader — dashboard map data
Authenticated-only endpoint — no module permission check (see AUTH_ONLY_SUFFIXES).

The leader's own district (and its state's name, which the frontend needs
to pick the boundary file) plus every ULB / RLB in that district, with the
month's collection figures. Payload shape: app/utils/leader_map.py.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.district import District
from app.models.masters.leader_management.district_leader_login import DistrictLeaderLogin
from app.models.superadmin.common_masters.state import State
from app.utils.leader_map import build_map_payload
from app.utils.leader_comparison import build_lb_comparison
from app.utils.leader_summary import build_summary


class DistrictBodyMapViewSet(ViewSet):
    throttle_scope = "district_body_dashboard"
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        district_id = getattr(user, "district_id", None) if isinstance(user, DistrictLeaderLogin) else None
        district = District.objects.filter(unique_id=district_id).first() if district_id else None
        if not district:
            return Response({"detail": "District not found for this leader."}, status=403)

        state = State.objects.filter(unique_id=district.state_id).first()
        return Response({
            "scope": "district",
            "state_id": district.state_id,
            "state_name": getattr(state, "name", "") or "",
            "district_id": district.unique_id,
            "district_name": district.name,
            **build_map_payload(request, state_id=district.state_id, district_id=district.unique_id),
        })


class DistrictBodySummaryViewSet(ViewSet):
    """Dashboard side panels (period KPIs, 7-day trend, waste-type split,
    grievances, fleet) for the leader's own district — app/utils/leader_summary.py."""
    throttle_scope = "district_body_dashboard"
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        district_id = getattr(user, "district_id", None) if isinstance(user, DistrictLeaderLogin) else None
        district = District.objects.filter(unique_id=district_id).first() if district_id else None
        if not district:
            return Response({"detail": "District not found for this leader."}, status=403)
        return Response({
            "scope": "district",
            "district_id": district.unique_id,
            **build_summary(request, state_id=district.state_id, district_id=district.unique_id),
        })


class _DistrictBodyComparisonViewSet(ViewSet):
    """Monthly / daily waste comparison per local body of the leader's own
    district — app/utils/leader_comparison.py."""
    throttle_scope = "district_body_dashboard"
    permission_classes = [IsAuthenticated]
    granularity = "month"

    def list(self, request):
        user = request.user
        district_id = getattr(user, "district_id", None) if isinstance(user, DistrictLeaderLogin) else None
        if not district_id or not District.objects.filter(unique_id=district_id).exists():
            return Response({"detail": "District not found for this leader."}, status=403)
        return Response({
            "district_id": district_id,
            **build_lb_comparison(request, district_id=district_id, granularity=self.granularity),
        })


class DistrictBodyMonthlyComparisonViewSet(_DistrictBodyComparisonViewSet):
    granularity = "month"


class DistrictBodyDailyComparisonViewSet(_DistrictBodyComparisonViewSet):
    granularity = "day"
