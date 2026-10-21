"""Superadmin Dashboard — every district and local body on the platform.

GET /api/v1/dashboard/superadmin/?date= | from_date=&to_date=
    &state_id=   one id or several, comma separated; narrows every section

Super admins only. Where the private build compared companies and projects,
this compares local bodies (corporations, municipalities, town panchayats,
panchayat unions, panchayats) and districts.
"""
from collections import Counter, defaultdict

from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.areatype import AreaType
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.district import District
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.ward import Ward
from app.models.superadmin.audits.login_audit import LoginAudit
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreenpermission import UserScreenPermission
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.models.superadmin_masters.auth_user import User
from app.services import dashboard_metrics as metrics
from app.viewsets.dashboard_admin_viewset import id_list
from app.utils.permission_catalog import MAINSCREEN_LABELS, SCREEN_LABELS, SCREEN_STRUCTURE

# UserScreenPermission.local_body_type -> flat-geo column.
LOCAL_BODY_TYPE_FIELDS = {
    "corporation": "corporation_id",
    "municipality": "municipality_id",
    "town_panchayat": "town_panchayat_id",
    "panchayat_union": "panchayat_union_id",
    "panchayat": "panchayat_id",
}
AREA_WIDE = "All local bodies"


def is_platform_super_admin(user):
    """The platform super admin account — the auth User that logs in with
    role "superadmin" (login_viewset). A staff record flagged is_superuser is
    still a tenant user (its role is its staff role), like private's
    superusers that belong to a company, and is refused."""
    return isinstance(user, User) and bool(user.is_superuser) and not user.is_deleted


class SuperAdminOnly(BasePermission):
    message = "Super admin only"

    def has_permission(self, request, view):
        return is_platform_super_admin(request.user)


class SuperadminDashboardViewSet(ViewSet):
    throttle_scope = "dashboard_summary"
    permission_classes = [IsAuthenticated, SuperAdminOnly]

    def list(self, request):
        params = request.query_params
        start, end = metrics.parse_range(params)
        states = list(
            State.objects.filter(is_deleted=False).order_by("name").values("unique_id", "name")
        )
        state_names = {s["unique_id"]: s["name"] for s in states}
        picked_states = tuple(s for s in id_list(params, "state_id") if s in state_names)
        scope = metrics.Scope(start=start, end=end, state_ids=picked_states)

        districts = list(metrics.scoped(District.objects.filter(is_deleted=False), scope).order_by("name"))
        district_names = {d.unique_id: d.name for d in districts}
        bodies = self._local_bodies(scope, district_names)
        body_names = {b["id"]: b["name"] for b in bodies}
        staff_bodies = self._staff_local_bodies(scope)

        grants = self._permission_grants(scope, body_names, district_names)
        staff_access = self._staff_access(scope, body_names, staff_bodies)
        logins = self._logins(scope, body_names, staff_bodies)
        breakdown = metrics.area_breakdown(scope, by="local_body")

        return Response({
            "scope": {
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "days": len(scope.days),
                "state_ids": list(picked_states),
                "state_name": ", ".join(state_names[s] for s in picked_states) or "All states",
            },
            "filters": {
                "states": [{"id": s["unique_id"], "name": s["name"]} for s in states],
            },
            "platform": self._platform(scope, districts, bodies),
            "operations": metrics.operations(scope),
            "staff": metrics.staff_summary(scope),
            "fleet": metrics.fleet_health(scope),
            "daily": metrics.daily_series(scope),
            "local_bodies": self._body_rows(bodies, breakdown, grants, staff_access, logins),
            "districts": self._district_rows(scope, districts, bodies),
            "staff_by_role": self._staff_by_role(scope, body_names, district_names),
            "permissions": {
                "catalog": [
                    {
                        "module": module,
                        "label": MAINSCREEN_LABELS.get(module, module),
                        "screens": [
                            {"name": name, "label": SCREEN_LABELS.get(name, name)}
                            for name in screens
                        ],
                    }
                    for module, screens in SCREEN_STRUCTURE.items()
                ],
                "local_body_grants": grants["rows"],
                "staff_grants": staff_access["by_screen"],
                "changes": self._permission_changes(scope, body_names, district_names),
            },
            "activity": logins["summary"],
            "masters": metrics.master_counts(scope, by="district"),
            "generated_at": timezone.now().isoformat(),
        })

    # ------------------------------------------------------------ platform

    def _local_bodies(self, scope, district_names):
        bodies = []
        for field, model, name_field, label in metrics.LOCAL_BODY_LEVELS:
            for row in (
                metrics.scoped(model.objects.filter(is_deleted=False), scope).order_by(name_field)
                .values("unique_id", name_field, "district_id", "is_active")
            ):
                bodies.append({
                    "id": row["unique_id"],
                    "name": row[name_field] or row["unique_id"],
                    "type": field,
                    "type_label": label,
                    "district_id": row["district_id"],
                    "district_name": district_names.get(row["district_id"], ""),
                    "is_active": row["is_active"],
                })
        return bodies

    def _platform(self, scope, districts, bodies):
        by_type = defaultdict(lambda: {"total": 0, "active": 0})
        for body in bodies:
            by_type[body["type_label"]]["total"] += 1
            by_type[body["type_label"]]["active"] += int(bool(body["is_active"]))

        def count(qs):
            return metrics.scoped(qs, scope).count()

        return {
            "states": count(State.objects.filter(is_deleted=False)),
            "districts": len(districts),
            "districts_active": sum(1 for d in districts if d.is_active),
            "area_types": count(AreaType.objects.filter(is_deleted=False)),
            "local_bodies": len(bodies),
            "local_bodies_active": sum(1 for b in bodies if b["is_active"]),
            "local_bodies_by_type": dict(by_type),
            "wards": count(Ward.objects.filter(is_deleted=False)),
            "customers": count(CustomerCreation.objects.filter(is_deleted=False)),
            "vehicles": count(VehicleCreation.objects.filter(is_deleted=False)),
            "platform_admins": User.objects.filter(is_superuser=True, is_deleted=False).count(),
            "staff_data_scopes": count(StaffDataScope.objects.filter(is_deleted=False, is_active=True)),
            "staff_access_configs": count(
                StaffAccessConfiguration.objects.filter(is_deleted=False, is_active=True),
            ),
            "modules": len(SCREEN_STRUCTURE),
            "screens": sum(len(s) for s in SCREEN_STRUCTURE.values()),
            "screens_seeded": UserScreen.objects.filter(is_deleted=False, is_active=True).count(),
            "app_modules": AppModule.objects.filter(is_deleted=False).count(),
        }

    def _staff_local_bodies(self, scope):
        """{staff_unique_id: local_body_id or ""} of the staff in scope."""
        return {
            row["staff_unique_id"]: metrics.local_body_of(row)
            for row in metrics.staff_qs(scope)
            .values("staff_unique_id", *metrics.LOCAL_BODY_FIELDS)
        }

    # --------------------------------------------------------- permissions

    def _names(self):
        mains = dict(MainScreen.objects.values_list("unique_id", "mainscreen_name"))
        screens = dict(UserScreen.objects.values_list("unique_id", "userscreen_name"))
        actions = dict(UserScreenAction.objects.values_list("unique_id", "action_name"))
        return mains, screens, actions

    def _permission_grants(self, scope, body_names, district_names):
        """Screens each local body is enabled for (the super-admin-owned
        UserScreenPermission rows). A row with no local body applies to the
        whole district / area it names."""
        mains, screens, actions = self._names()
        tree = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        for body_type, body_id, district_id, main_id, screen_id, action_id in (
            UserScreenPermission.objects.filter(
                is_deleted=False, is_active=True,
                permission_type="screen", permission_owner_kind="super_admin",
            ).values_list(
                "local_body_type", "local_body_id", "district_id",
                "mainscreen_id", "userscreen_id", "userscreenaction_id",
            )
        ):
            module = mains.get(main_id)
            screen = screens.get(screen_id)
            if not module or not screen:
                continue
            if scope.state_ids and (
                body_id not in body_names if body_id
                else district_id and district_id not in district_names
            ):
                continue  # another state's local body / district
            key = (body_type or "", body_id or "", "" if body_id else (district_id or ""))
            tree[key][module][screen].add(actions.get(action_id) or "?")

        catalog = {(m, s) for m, ss in SCREEN_STRUCTURE.items() for s in ss}
        catalog_total = len(catalog)
        rows, per_body = [], defaultdict(set)
        for (body_type, body_id, district_id), modules in sorted(
            tree.items(),
            key=lambda item: (body_names.get(item[0][1], "~"), district_names.get(item[0][2], "")),
        ):
            screen_keys = {(m, s) for m, ss in modules.items() for s in ss}
            if body_id:
                per_body[body_id] |= screen_keys & catalog
            rows.append({
                "local_body_id": body_id,
                "local_body_type": body_type,
                "local_body_name": (
                    body_names.get(body_id, body_id) if body_id
                    else f"{AREA_WIDE} · {district_names.get(district_id, 'Platform')}"
                    if district_id else f"{AREA_WIDE} · Platform"
                ),
                "screens_enabled": len(screen_keys & catalog),
                # Legacy screens outside the catalog are listed but do not
                # count towards coverage, so it never passes 100%.
                "coverage": metrics.pct(len(screen_keys & catalog), catalog_total),
                "modules": [
                    {
                        "module": module,
                        "label": MAINSCREEN_LABELS.get(module, module),
                        "screens": [
                            {"name": s, "label": SCREEN_LABELS.get(s, s), "actions": sorted(a)}
                            for s, a in sorted(ss.items())
                        ],
                    }
                    for module, ss in sorted(modules.items())
                ],
            })
        return {
            "rows": rows,
            "body_screens": {k: len(v) for k, v in per_body.items()},
            "body_modules": {k: len({m for m, _ in v}) for k, v in per_body.items()},
            "catalog_total": catalog_total,
        }

    def _staff_access(self, scope, body_names, staff_bodies):
        """Staff access configurations per local body (the staff's own local
        body), and how many staff hold `view` on each screen."""
        configs = {
            row["unique_id"]: row
            for row in metrics.scoped(
                StaffAccessConfiguration.objects.filter(is_deleted=False, is_active=True), scope,
            ).values("unique_id", "staff_id")
        }
        mains, screens, actions = self._names()
        holders = defaultdict(lambda: defaultdict(set))  # body -> (module, screen) -> staff
        per_config = Counter()
        for config_id, main_id, screen_id, action_id in (
            StaffAccessConfigurationPermission.objects.filter(
                is_deleted=False, staff_access_configuration_id__in=configs.keys(),
            ).values_list("staff_access_configuration_id", "mainscreen_id", "userscreen_id", "userscreenaction_id")
        ):
            config = configs.get(config_id)
            per_config[config_id] += 1
            if actions.get(action_id) != "view":
                continue
            key = (mains.get(main_id), screens.get(screen_id))
            if None in key:
                continue
            holders[staff_bodies.get(config["staff_id"], "")][key].add(config["staff_id"])

        body_of = {cid: staff_bodies.get(c["staff_id"], "") for cid, c in configs.items()}
        configured = Counter(body_of.values())
        empty = Counter(body_of[cid] for cid in configs if not per_config[cid])
        grants = Counter()
        for cid in configs:
            grants[body_of[cid]] += per_config[cid]
        by_screen = [
            {
                "local_body_id": body_id,
                "local_body_name": body_names.get(body_id, body_id) if body_id else "Not linked to a local body",
                "module": module,
                "module_label": MAINSCREEN_LABELS.get(module, module),
                "screen": screen,
                "screen_label": SCREEN_LABELS.get(screen, screen),
                "staff_with_view": len(staff),
            }
            for body_id, keys in holders.items()
            for (module, screen), staff in sorted(keys.items())
        ]
        return {
            "configured": configured,
            "without_grants": empty,
            "avg_grants": {
                body_id: round(grants[body_id] / n, 1) for body_id, n in configured.items() if n
            },
            "by_screen": by_screen,
        }

    def _permission_changes(self, scope, body_names, district_names):
        start_dt, end_dt = scope.window
        changes = PermissionAuditLog.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt)
        if scope.state_ids:
            changes = changes.filter(
                Q(state_id__in=scope.state_ids)
                | Q(district_id__in=list(district_names))
                | Q(local_body_id__in=list(body_names))
            )
        per_day = metrics.day_counts(changes.values_list("timestamp", flat=True), scope)
        by_area = Counter()
        for body_id, district_id in changes.values_list("local_body_id", "district_id"):
            if body_id:
                by_area[body_names.get(body_id, body_id)] += 1
            elif district_id:
                by_area[f"{AREA_WIDE} · {district_names.get(district_id, district_id)}"] += 1
            else:
                by_area["Platform"] += 1
        return {
            "total": changes.count(),
            "by_source": metrics.counts_by(changes, "source"),
            "by_action": metrics.counts_by(changes, "action_type"),
            "by_local_body": dict(by_area.most_common()),
            "per_day": [
                {"date": day.isoformat(), "changes": per_day.get(day, 0)} for day in scope.days
            ],
        }

    # ------------------------------------------------------------ activity

    def _logins(self, scope, body_names, staff_bodies):
        """Sign-ins attributed to the signing-in staff's local body. Login
        audit rows carry no geography; non-staff sign-ins (platform, leaders,
        customers) are grouped under their login module."""
        start_dt, end_dt = scope.window
        logins = LoginAudit.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt)
        if scope.state_ids:
            # Audit rows carry no geography: only the state's staff count.
            logins = logins.filter(user_unique_id__in=list(staff_bodies))
        ok, failed = Counter(), Counter()
        per_body = defaultdict(lambda: {"ok": 0, "failed": 0, "users": set()})
        for stamp, success, user_id, username, module_name in logins.values_list(
            "timestamp", "success", "user_unique_id", "username", "module_name",
        ):
            day = timezone.localtime(stamp).date()
            (ok if success else failed)[day] += 1
            body = staff_bodies.get(user_id)
            key = body if body else f"~{(module_name or 'other').title()}"
            row = per_body[key]
            row["ok" if success else "failed"] += 1
            if success:
                row["users"].add(username)

        last_login = defaultdict(lambda: None)
        for user_id, last in (
            LoginAudit.objects.filter(success=True, user_unique_id__in=list(staff_bodies))
            .order_by().values("user_unique_id").annotate(last=Max("timestamp"))
            .values_list("user_unique_id", "last")
        ):
            body = staff_bodies.get(user_id)
            if body and (last_login[body] is None or last > last_login[body]):
                last_login[body] = last

        def label(key):
            if key.startswith("~"):
                return f"{key[1:]} sign-ins"
            return body_names.get(key, key)

        return {
            "per_body": per_body,
            "last_login": last_login,
            "summary": {
                "logins": sum(ok.values()),
                "failed_logins": sum(failed.values()),
                "active_users": logins.filter(success=True).values("username").distinct().count(),
                "per_day": [
                    {"date": d.isoformat(), "success": ok.get(d, 0), "failed": failed.get(d, 0)}
                    for d in scope.days
                ],
                "by_local_body": [
                    {
                        "local_body_id": "" if key.startswith("~") else key,
                        "local_body_name": label(key),
                        "success": row["ok"],
                        "failed": row["failed"],
                        "users": len(row["users"]),
                    }
                    for key, row in sorted(per_body.items(), key=lambda i: -i[1]["ok"])
                ],
            },
        }

    # -------------------------------------------------------- local bodies

    def _body_rows(self, bodies, breakdown, grants, staff_access, logins):
        """One row per local body that has anything to show — a state holds
        thousands of panchayats, most of them without records yet."""
        staff = StaffcreationOfficeDetails.objects.filter(is_deleted=False)
        staff_counts = defaultdict(Counter)
        for row in staff.values("is_active", "active_status", "login_enabled", *metrics.LOCAL_BODY_FIELDS):
            body = metrics.local_body_of(row)
            staff_counts[body]["total"] += 1
            staff_counts[body]["active"] += int(bool(row["is_active"] and row["active_status"]))
            staff_counts[body]["login_enabled"] += int(bool(row["login_enabled"]))
        wards = metrics.per_local_body(Ward.objects.filter(is_deleted=False))

        out = []
        for body in bodies:
            bid = body["id"]
            ops = breakdown.get(bid)
            s = staff_counts.get(bid, Counter())
            login = logins["per_body"].get(bid)
            screens = grants["body_screens"].get(bid, 0)
            if not (ops or s or login or screens):
                continue
            ops = ops or metrics.EMPTY_AREA_ROW
            last = logins["last_login"].get(bid)
            out.append({
                "local_body_id": bid,
                "local_body_name": body["name"],
                "type_label": body["type_label"],
                "district_id": body["district_id"],
                "district_name": body["district_name"],
                "is_active": body["is_active"],
                "wards": wards.get(bid, 0),
                "staff": s["total"],
                "staff_active": s["active"],
                "staff_login_enabled": s["login_enabled"],
                "staff_configured": staff_access["configured"].get(bid, 0),
                "staff_without_grants": staff_access["without_grants"].get(bid, 0),
                "avg_grants_per_staff": staff_access["avg_grants"].get(bid, 0),
                "screens_enabled": screens,
                "modules_enabled": grants["body_modules"].get(bid, 0),
                "screen_coverage": metrics.pct(screens, grants["catalog_total"]),
                "customers": ops["customers"],
                "vehicles": ops["vehicles"],
                "bins": ops["bins"],
                "trips": ops["trips"],
                "trips_completed": ops["trips_completed"],
                "completion_rate": ops["completion_rate"],
                "trip_logs": ops["trip_logs"],
                "total_kg": ops["total_kg"],
                "breakdowns": ops["breakdowns"],
                "open_complaints": ops["open_complaints"],
                "logins": login["ok"] if login else 0,
                "failed_logins": login["failed"] if login else 0,
                "last_login": last.isoformat() if last else None,
            })
        return out

    def _district_rows(self, scope, districts, bodies):
        breakdown = metrics.area_breakdown(scope, by="district")
        body_counts = Counter(b["district_id"] for b in bodies)
        wards = metrics.per_district(Ward.objects.filter(is_deleted=False))
        state_names = dict(State.objects.values_list("unique_id", "name"))
        out = []
        for district in districts:
            did = district.unique_id
            out.append({
                "district_id": did,
                "district_name": district.name,
                "state_name": state_names.get(district.state_id, ""),
                "is_active": district.is_active,
                "local_bodies": body_counts.get(did, 0),
                "wards": wards.get(did, 0),
                **breakdown.get(did, metrics.EMPTY_AREA_ROW),
            })
        return out

    def _staff_by_role(self, scope, body_names, district_names):
        names = metrics.role_names()
        counts = Counter()
        for row in metrics.staff_qs(scope).values(
            "district_id", "governmentusertype_id", "staffusertype_id", "contractorusertype_id",
            *metrics.LOCAL_BODY_FIELDS,
        ):
            counts[(row["district_id"] or "", metrics.local_body_of(row), metrics.staff_role(row, names))] += 1
        return [
            {
                "district_id": district_id,
                "district_name": district_names.get(district_id, "—"),
                "local_body_id": body_id,
                "local_body_name": body_names.get(body_id, "—") if body_id else "District / state level",
                "role": role,
                "staff": n,
            }
            for (district_id, body_id, role), n in sorted(
                counts.items(),
                key=lambda i: (district_names.get(i[0][0], "~"), body_names.get(i[0][1], "~"), i[0][2]),
            )
        ]
