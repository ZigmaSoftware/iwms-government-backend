"""
State Leader Dashboard API
Authenticated-only endpoint — no module permission check (see AUTH_ONLY_SUFFIXES).

Data source: District masters belonging to the leader's State.

Trip-level collection analytics (actual weight, monthly/daily comparison,
waste-type breakdown) are served separately by
StateMonthlyWasteComparisonViewSet / StateDailyWasteComparisonViewSet
(statebody_waste_comparison_viewset.py) — DailyTripLog carries a direct,
auto-populated `state_id` column, so it can be filtered/aggregated by state
directly.
"""
from decimal import Decimal, ROUND_HALF_UP

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.state_leader_login import StateLeaderLogin
from app.models.masters.district import District


TWO = Decimal("0.01")


def _r(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


class StateBodyDashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    # ── helpers ─────────────────────────────────────────────────────────

    def _get_leader(self, request):
        user = request.user
        if isinstance(user, StateLeaderLogin):
            return user
        return None

    def _get_state(self, request):
        leader = self._get_leader(request)
        if leader:
            return getattr(leader, "state_id", None)
        return None

    # ── main endpoint ───────────────────────────────────────────────────

    def list(self, request):
        state = self._get_state(request)
        if not state:
            return Response(
                {"detail": "State not found for this leader."}, status=403
            )

        state_uid  = state.unique_id
        state_name = getattr(state, "name", "") or ""

        districts = District.objects.filter(
            state_id=state_uid,
            is_deleted=False,
        ).order_by("name")

        district_rows = [
            {
                "district_id":   d.unique_id,
                "district_name": d.name,
                "is_active":     d.is_active,
            }
            for d in districts
        ]

        return Response({
            "state_id":     state_uid,
            "state_name":   state_name,
            "districts":    district_rows,
            "kpis": {
                "total_districts": len(district_rows),
            },
        })
