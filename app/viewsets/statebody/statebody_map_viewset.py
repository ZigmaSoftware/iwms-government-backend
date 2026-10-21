"""
State Leader — dashboard map data
Authenticated-only endpoint — no module permission check (see AUTH_ONLY_SUFFIXES).

Every district of the leader's own state plus every ULB / RLB in it, with
the month's collection figures. Payload shape: app/utils/leader_map.py.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.district import District
from app.models.masters.leader_management.state_leader_login import StateLeaderLogin
from app.models.superadmin.common_masters.state import State
from app.utils.leader_map import build_map_payload
from app.utils.leader_summary import build_summary


class StateBodyMapViewSet(ViewSet):
    throttle_scope = "state_body_dashboard"
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        state_id = getattr(user, "state_id", None) if isinstance(user, StateLeaderLogin) else None
        if not state_id:
            return Response({"detail": "State not found for this leader."}, status=403)

        state = State.objects.filter(unique_id=state_id).first()
        return Response({
            "scope": "state",
            "state_id": state_id,
            "state_name": getattr(state, "name", "") or "",
            **build_map_payload(request, state_id=state_id),
        })


class StateBodySummaryViewSet(ViewSet):
    """Dashboard side panels (period KPIs, 7-day trend, waste-type split,
    grievances, fleet) for the leader's own state — app/utils/leader_summary.py."""
    throttle_scope = "state_body_dashboard"
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        state_id = getattr(user, "state_id", None) if isinstance(user, StateLeaderLogin) else None
        if not state_id:
            return Response({"detail": "State not found for this leader."}, status=403)
        # optional ?district_id= narrows the panels to one district — only one
        # that belongs to the leader's own state
        district_id = request.query_params.get("district_id") or None
        if district_id and not District.objects.filter(unique_id=district_id, state_id=state_id, is_deleted=False).exists():
            return Response({"detail": "District not found in your state."}, status=404)
        return Response({
            "scope": "district" if district_id else "state",
            "state_id": state_id,
            "district_id": district_id,
            **build_summary(request, state_id=state_id, district_id=district_id),
        })
