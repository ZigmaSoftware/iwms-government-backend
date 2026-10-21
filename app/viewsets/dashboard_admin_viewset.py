"""Admin Dashboard — operations for the geography the caller is scoped to.

GET /api/v1/dashboard/admin/
    ?state_id=       one id or several, comma separated
    &district_id=    one id or several, comma separated
    &local_body_id=  corporation / municipality / town panchayat / panchayat
                     union / panchayat ids, any mix, comma separated
    &ward_id=        wards of the picked local bodies
    &date=           one day, or
    &from_date=&to_date=   an inclusive range

Every pick is capped by the caller's StaffDataScope: a staff scoped to two
corporations only ever sees (and may only pick) those two. Super admins see
the whole platform. Omitted picks mean "everything in scope".
"""
from django.utils import timezone
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.middleware.module_permission_middleware import (
    ModulePermissionMiddleware,
    _resolve_permissions_for_request,
)
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.services import dashboard_metrics as metrics
from app.utils.hierarchy import _granted_scope_level, _staff_scope


# A state scope holds thousands of panchayats; past this many local bodies the
# picker lists them only once districts are picked.
LOCAL_BODY_PICKER_LIMIT = 1000


def id_list(params, key):
    """`?key=a,b` and `?key=a&key=b` -> ("a", "b"); blanks dropped."""
    values = []
    for raw in params.getlist(key):
        values += [v.strip() for v in raw.split(",") if v.strip()]
    return tuple(dict.fromkeys(values))


def is_super_admin(user):
    return bool(getattr(user, "is_superuser", False))


class HasDashboardGrant(BasePermission):
    """Super admins, or staff holding `view` on the dashboard / dashboard
    screen — the grant the sidebar "Dashboard" entry and AdminHomeGate check.

    The `dashboard` route group is not a ModulePermissionMiddleware module,
    so the grant is checked here, through the middleware's own resolver.
    Non-staff users (leaders, customers) are refused outright: the
    requester-scope filter would pass their querysets through unfiltered."""

    message = "Dashboard permission required"

    def has_permission(self, request, view):
        user = request.user
        if is_super_admin(user):
            return True
        if not getattr(user, "staff_unique_id", None):
            return False
        middleware = ModulePermissionMiddleware(get_response=lambda request: None)
        permissions = _resolve_permissions_for_request(request)
        return "view" in middleware._owner_actions(permissions, "dashboard", "dashboard")


class AdminDashboardViewSet(ViewSet):
    throttle_scope = "dashboard_summary"
    permission_classes = [IsAuthenticated, HasDashboardGrant]

    def _visible(self, base):
        """States, districts and local bodies the caller may see, for the
        pickers."""
        states = list(
            metrics.scoped(State.objects.filter(is_deleted=False, is_active=True), base)
            .order_by("name").values("unique_id", "name")
        )
        districts = list(
            metrics.scoped(District.objects.filter(is_deleted=False, is_active=True), base)
            .order_by("name").values("unique_id", "name", "state_id")
        )
        district_names = {d["unique_id"]: d["name"] for d in districts}
        bodies = []
        for field, model, name_field, label in metrics.LOCAL_BODY_LEVELS:
            for row in (
                metrics.scoped(model.objects.filter(is_deleted=False, is_active=True), base)
                .order_by(name_field).values("unique_id", name_field, "district_id", "state_id")
            ):
                bodies.append({
                    "id": row["unique_id"],
                    "name": row[name_field] or row["unique_id"],
                    "type": field,
                    "type_label": label,
                    "district_id": row["district_id"],
                    "district_name": district_names.get(row["district_id"], ""),
                    "state_id": row["state_id"],
                })
        return states, districts, bodies

    def _scope(self, request):
        params = request.query_params
        start, end = metrics.parse_range(params)
        user = request.user
        base = metrics.Scope(start=start, end=end, user=user)
        states, all_districts, bodies = self._visible(base)

        visible_states = {s["unique_id"] for s in states}
        picked_states = tuple(s for s in id_list(params, "state_id") if s in visible_states)
        # Picking states narrows the district picker (and its picks).
        districts = [d for d in all_districts if not picked_states or d["state_id"] in picked_states]
        visible_districts = {d["unique_id"] for d in districts}
        picked_districts = tuple(d for d in id_list(params, "district_id") if d in visible_districts)

        candidates = [
            b for b in bodies
            if (not picked_states or b["state_id"] in picked_states)
            and (not picked_districts or b["district_id"] in picked_districts)
        ]
        wanted = set(id_list(params, "local_body_id"))
        selected = [b for b in candidates if b["id"] in wanted]
        # A staff with a single local body has nothing to pick: it is the
        # selection (see `can_pick_local_body`).
        if not is_super_admin(user) and len(bodies) == 1:
            selected = bodies

        wards = []
        if selected:
            ward_qs = metrics.scoped(
                Ward.objects.filter(is_deleted=False, is_active=True),
                metrics.Scope(start=start, end=end, user=user, local_bodies=_by_level(selected)),
            )
            wards = [
                {"id": w["unique_id"], "name": w["ward_name"] or w["unique_id"],
                 "local_body_id": metrics.local_body_of(w)}
                for w in ward_qs.order_by("ward_name").values(
                    "unique_id", "ward_name", *metrics.LOCAL_BODY_FIELDS,
                )
            ]
        visible_wards = {w["id"] for w in wards}
        picked_wards = tuple(w for w in id_list(params, "ward_id") if w in visible_wards)

        scope = metrics.Scope(
            start=start, end=end, user=user,
            state_ids=picked_states,
            district_ids=picked_districts,
            local_bodies=_by_level(selected),
            ward_ids=picked_wards,
        )
        return scope, states, districts, bodies, candidates, selected, wards

    def list(self, request):
        scope, states, districts, bodies, candidates, selected, wards = self._scope(request)
        state_names = {s["unique_id"]: s["name"] for s in states}
        district_names = {d["unique_id"]: d["name"] for d in districts}
        ward_names = {w["id"]: w["name"] for w in wards}
        staff_scope = _staff_scope(request.user)

        # Comparison table: the picked local bodies, else every one in view
        # that has any activity or records (a state scope holds thousands of
        # panchayats, most of them empty).
        breakdown = metrics.area_breakdown(scope, by="local_body")
        shown = selected or candidates
        rows = []
        for body in shown:
            values = breakdown.get(body["id"])
            if values is None and not selected:
                continue
            rows.append({
                "local_body_id": body["id"],
                "local_body_name": body["name"],
                "type_label": body["type_label"],
                "district_id": body["district_id"],
                "district_name": body["district_name"],
                **(values or metrics.EMPTY_AREA_ROW),
            })
        needs_district = len(candidates) > LOCAL_BODY_PICKER_LIMIT
        picker = candidates if not needs_district else [
            b for b in candidates if b["id"] in {s["id"] for s in selected}
        ]

        unlinked = breakdown.get("")
        if unlinked and not selected and not scope.district_ids and not scope.state_ids:
            rows.append({
                "local_body_id": "",
                "local_body_name": "Not linked to a local body",
                "type_label": "",
                "district_id": "",
                "district_name": "",
                **unlinked,
            })

        return Response({
            "scope": {
                "state_ids": list(scope.state_ids),
                "state_name": (
                    ", ".join(state_names.get(s, s) for s in scope.state_ids)
                    or ("All states" if len(states) != 1 else states[0]["name"])
                ),
                "district_ids": list(scope.district_ids),
                "district_name": (
                    ", ".join(district_names.get(d, d) for d in scope.district_ids)
                    or ("All districts" if len(districts) != 1 else districts[0]["name"])
                ),
                "local_body_ids": [b["id"] for b in selected],
                "local_body_name": (
                    ", ".join(b["name"] for b in selected) or "All local bodies"
                ),
                "ward_ids": list(scope.ward_ids),
                "ward_name": ", ".join(ward_names.get(w, w) for w in scope.ward_ids) or "All wards",
                "granted_level": (
                    "platform" if is_super_admin(request.user)
                    else _granted_scope_level(staff_scope) if staff_scope else None
                ),
                "from_date": scope.start.isoformat(),
                "to_date": scope.end.isoformat(),
                "days": len(scope.days),
            },
            "filters": {
                "can_pick_state": len(states) > 1,
                "states": [{"id": s["unique_id"], "name": s["name"]} for s in states],
                "can_pick_district": len(districts) > 1,
                "can_pick_local_body": is_super_admin(request.user) or len(bodies) > 1,
                "can_pick_ward": bool(wards),
                # The picked states' districts, or every one in scope.
                "districts": [
                    {"id": d["unique_id"], "name": d["name"], "state_id": d["state_id"]}
                    for d in districts
                ],
                # The picked districts' local bodies (or every one in scope);
                # empty with `local_bodies_need_district` when there are too
                # many to list — the picked ones are always included.
                "local_bodies": picker,
                "local_bodies_need_district": needs_district,
                "wards": wards,
            },
            "operations": metrics.operations(scope),
            "fleet": metrics.fleet_health(scope),
            "staff": metrics.staff_summary(scope),
            "daily": metrics.daily_series(scope),
            "top": metrics.top_performers(scope),
            "local_bodies": rows,
            "masters": metrics.master_counts(scope, by="local_body"),
            "generated_at": timezone.now().isoformat(),
        })


def _by_level(bodies):
    """[{id, type}, ...] -> (("corporation_id", ("CORP-1", ...)), ...)."""
    grouped = {}
    for body in bodies:
        grouped.setdefault(body["type"], []).append(body["id"])
    return tuple((field, tuple(ids)) for field, ids in grouped.items())
