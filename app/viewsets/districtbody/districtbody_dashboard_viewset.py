"""
District Leader Dashboard API
Authenticated-only endpoint — no module permission check (see AUTH_ONLY_SUFFIXES).

Data source: Panchayat masters belonging to the leader's District.
  agreed_weight   = Panchayat.agreed_weight_kg (daily target), per panchayat.

Note: trip-level analytics (actual collected weight, variance, etc. — as done
in LocalBodyDashboardViewSet for a single panchayat) are intentionally NOT
computed here. DailyTripLog has no panchayat_id/district_id column — it is
only scoped via `location_node` — so it cannot be filtered/aggregated by a
static district_id the way the panchayat dashboard's DailyTripLog query does
(that query already relies on a non-existent field). Until trip logs carry a
resolvable district scope, this endpoint reports district/panchayat
configuration only and surfaces a placeholder for trip analytics.
"""
from decimal import Decimal, ROUND_HALF_UP

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.leader_management.district_leader_login import DistrictLeaderLogin
from app.models.masters.panchayat import Panchayat


TWO = Decimal("0.01")


def _r(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


class DistrictBodyDashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    # ── helpers ─────────────────────────────────────────────────────────

    def _get_leader(self, request):
        user = request.user
        if isinstance(user, DistrictLeaderLogin):
            return user
        return None

    def _get_district(self, request):
        leader = self._get_leader(request)
        if leader:
            return getattr(leader, "district_id", None)
        return None

    # ── main endpoint ───────────────────────────────────────────────────

    def list(self, request):
        district = self._get_district(request)
        if not district:
            return Response(
                {"detail": "District not found for this leader."}, status=403
            )

        district_uid  = district.unique_id
        district_name = getattr(district, "name", "") or ""

        panchayats = Panchayat.objects.filter(
            district_id=district_uid,
            is_deleted=False,
        ).order_by("panchayat_name")

        panchayat_rows = [
            {
                "panchayat_id":       p.unique_id,
                "panchayat_name":     p.panchayat_name,
                "agreed_weight_kg":   float(_r(p.agreed_weight_kg)),
                "is_active":          p.is_active,
            }
            for p in panchayats
        ]

        total_agreed_weight = sum(
            (Decimal(str(row["agreed_weight_kg"])) for row in panchayat_rows),
            Decimal("0"),
        )

        return Response({
            "district_id":         district_uid,
            "district_name":       district_name,
            "panchayats":          panchayat_rows,
            "kpis": {
                "total_panchayats":     len(panchayat_rows),
                "total_agreed_weight":  float(_r(total_agreed_weight)),
            },
            # Trip-level collection analytics are not available at the district
            # scope yet — see module docstring.
            "trip_analytics": None,
            "trip_analytics_note": (
                "Trip collection analytics are not available for district-level "
                "reporting yet: DailyTripLog records are scoped only by "
                "location_node, not by panchayat_id/district_id."
            ),
        })
