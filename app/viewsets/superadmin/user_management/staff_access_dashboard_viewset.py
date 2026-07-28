from collections import defaultdict
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.core_modules.attendance.daily_attendance_reg import DailyAttendanceReg
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.screen_management.companyuserscreenpermission import (
    UserScreenPermission,
)
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails
from app.models.superadmin.user_management.staff_data_scope import StaffDataScope
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_requester_scope,
    filter_staff_queryset_by_requester_scope,
)


SCOPE_CONFIG = {
    "district": {
        "model": District,
        "name": "name",
        "staff_field": "district",
        "scope_m2m": None,
        "geo_field": "district",
        "label": "District",
        "relations": ("state_id",),
    },
    "corporation": {
        "model": Corporation,
        "name": "corporation_name",
        "staff_field": "corporation",
        "scope_m2m": "corporations",
        "geo_field": "corporation",
        "label": "Corporation",
        "relations": ("state_id", "district_id", "area_type_id"),
    },
    "panchayat_union": {
        "model": PanchayatUnion,
        "name": "union_name",
        "staff_field": "panchayat_union",
        "scope_m2m": "panchayat_unions",
        "geo_field": "panchayat_union",
        "label": "Panchayat Union",
        "relations": ("state_id", "district_id", "area_type_id"),
    },
    "panchayat": {
        "model": Panchayat,
        "name": "panchayat_name",
        "staff_field": "panchayat",
        "scope_m2m": "panchayats",
        "geo_field": "panchayat",
        "label": "Panchayat",
        "relations": ("state_id", "district_id", "area_type_id"),
    },
}

ALLOWED_ORDERING = {
    "employee_name",
    "-employee_name",
    "emp_id",
    "-emp_id",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
}


def _active(queryset):
    model = queryset.model
    field_names = {field.name for field in model._meta.get_fields()}
    if "is_deleted" in field_names:
        queryset = queryset.filter(is_deleted=False)
    if "is_active" in field_names:
        queryset = queryset.filter(is_active=True)
    return queryset


def _role_name(staff):
    for field in (
        "governmentusertype_id",
        "staffusertype_id",
        "contractorusertype_id",
        "user_type_id",
    ):
        role = getattr(staff, field, None)
        if role:
            return getattr(role, "name", None) or str(role)
    return ""


def _multi_values(params, key):
    values = []
    for raw in params.getlist(key):
        values.extend(
            item.strip() for item in str(raw).split(",") if item.strip()
        )
    return list(dict.fromkeys(values))


class StaffAccessDashboardViewSet(ViewSet):
    """Read-only, scope-safe staff access and operational assignment dashboard."""

    permission_classes = [IsAuthenticated]
    permission_resource = "StaffAccessDashboard"

    def list(self, request):
        access_context = self._requester_access_context(request)
        requested_scope_type = request.query_params.get(
            "scope_type", "corporation"
        ).strip()
        scope_type = (
            access_context.get("scope_type")
            if access_context.get("locked") and access_context.get("scope_type")
            else requested_scope_type
        )
        if scope_type not in SCOPE_CONFIG:
            raise ValidationError(
                {
                    "scope_type": (
                        "Use district, corporation, panchayat_union, or panchayat."
                    )
                }
            )

        date_from, date_to = self._date_range(request)
        config = SCOPE_CONFIG[scope_type]
        selected_admin = self._selected_admin(
            request,
            forced_admin_id=(
                access_context.get("admin_id")
                if access_context.get("locked")
                else None
            ),
        )
        scopes = self._scope_queryset(request, scope_type, selected_admin)
        scope_id = (
            access_context.get("scope_id") or ""
            if access_context.get("locked") and access_context.get("scope_id")
            else request.query_params.get("scope_id", "").strip()
        )
        selected_scope = self._selected_scope(config, scopes, scope_id)

        staff = self._staff_queryset(request, config, scope_id, selected_admin)
        permission_counts = self._permission_counts(staff)
        summary = self._staff_summary(staff, permission_counts)

        assignment_payload = self._assignment_payload(
            request,
            config,
            selected_scope,
            staff,
            date_from,
            date_to,
        )

        return Response(
            {
                "filters": self._filters(
                    request,
                    scope_type,
                    selected_admin,
                    selected_scope,
                ),
                "summary": {
                    "total_scopes": scopes.count(),
                    **summary,
                },
                "scope_rows": self._scope_rows(
                    request, scope_type, scopes, selected_admin
                ),
                "selected_admin": self._admin_ref(
                    selected_admin,
                    selected_scope=selected_scope,
                    selected_scope_type=scope_type,
                )
                if selected_admin
                else None,
                "access_context": access_context,
                "selected_scope": self._scope_ref(config, selected_scope)
                if selected_scope
                else None,
                "kpis": summary if selected_scope else None,
                "staff_rows": self._staff_rows(request, staff, permission_counts),
                **assignment_payload,
                # Waste comparison is intentionally fetched from the existing,
                # unchanged report endpoints by the frontend.
                "daily_waste_comparison": None,
                "monthly_waste_comparison": None,
                "as_of": timezone.now().isoformat(),
            }
        )

    def _requester_access_context(self, request):
        if getattr(request.user, "is_superuser", False):
            return {
                "locked": False,
                "admin_id": None,
                "scope_type": None,
                "scope_id": None,
                "hierarchy_label": "",
            }
        staff_id = getattr(request.user, "staff_unique_id", None)
        if not staff_id:
            staff_id = getattr(
                getattr(request.user, "staff", None),
                "staff_unique_id",
                None,
            )
        staff = (
            StaffcreationOfficeDetails.objects.select_related(
                "governmentusertype_id",
            )
            .prefetch_related(
                "data_scopes__corporations",
                "data_scopes__panchayat_unions",
                "data_scopes__panchayats",
            )
            .filter(staff_unique_id=staff_id, is_deleted=False)
            .first()
        )
        if not staff:
            return {
                "locked": False,
                "admin_id": None,
                "scope_type": None,
                "scope_id": None,
                "hierarchy_label": "",
            }
        scope = self._active_data_scope(staff)
        if not scope:
            return {
                "locked": True,
                "admin_id": staff.staff_head_id or None,
                "scope_type": None,
                "scope_id": None,
                "hierarchy_label": "No active data scope",
            }

        hierarchy = []
        if scope.state:
            hierarchy.append(scope.state.name)
        if scope.district:
            hierarchy.append(scope.district.name)
        resolved_type = None
        resolved_id = None
        for scope_type, relation, name_field in (
            ("panchayat", "panchayats", "panchayat_name"),
            ("panchayat_union", "panchayat_unions", "union_name"),
            ("corporation", "corporations", "corporation_name"),
        ):
            entries = list(getattr(scope, relation).all())
            if not entries:
                continue
            hierarchy.extend(getattr(item, name_field) for item in entries)
            if resolved_type is None:
                resolved_type = scope_type
                # A single configured body is immutable. Multiple bodies stay
                # selectable, but the backend still limits them to this scope.
                resolved_id = entries[0].unique_id if len(entries) == 1 else None
        if resolved_type is None and scope.district_id:
            resolved_type = "district"
            resolved_id = scope.district_id

        role_name = getattr(
            getattr(staff, "governmentusertype_id", None),
            "name",
            "",
        )
        return {
            "locked": True,
            "admin_id": (
                staff.staff_unique_id
                if role_name.endswith("_admin")
                else staff.staff_head_id or None
            ),
            "scope_type": resolved_type,
            "scope_id": resolved_id,
            "hierarchy_label": " → ".join(hierarchy),
        }

    def _admin_queryset(self, request):
        queryset = StaffcreationOfficeDetails.objects.select_related(
            "governmentusertype_id",
            "state",
            "district",
            "area_type",
            "corporation",
            "panchayat_union",
            "panchayat",
        ).prefetch_related(
            "data_scopes__corporations",
            "data_scopes__panchayat_unions",
            "data_scopes__panchayats",
            "data_scopes__wards",
        ).filter(
            active_status=True,
            login_enabled=True,
            is_deleted=False,
            governmentusertype_id__name__endswith="_admin",
        )
        if getattr(request.user, "is_superuser", False):
            return queryset.order_by("employee_name")
        requester_id = getattr(request.user, "staff_unique_id", None)
        scoped = filter_staff_queryset_by_requester_scope(queryset, request.user)
        if requester_id:
            scoped = queryset.filter(
                Q(staff_unique_id=requester_id)
                | Q(staff_unique_id__in=scoped.values("staff_unique_id"))
            )
        return scoped.distinct().order_by("employee_name")

    def _selected_admin(self, request, forced_admin_id=None):
        admin_id = (
            forced_admin_id
            or request.query_params.get("admin_id", "").strip()
        )
        if not admin_id:
            return None
        selected = self._admin_queryset(request).filter(
            staff_unique_id=admin_id
        ).first()
        if selected:
            return selected
        if StaffcreationOfficeDetails.objects.filter(
            staff_unique_id=admin_id,
            governmentusertype_id__name__endswith="_admin",
        ).exists():
            raise PermissionDenied("The selected admin is outside your access.")
        raise ValidationError({"admin_id": "Unknown admin."})

    def _active_data_scope(self, staff):
        return next(
            (
                scope
                for scope in staff.data_scopes.all()
                if scope.is_active and not scope.is_deleted
            ),
            None,
        )

    def _admin_ref(
        self,
        admin,
        selected_scope=None,
        selected_scope_type=None,
    ):
        scope = self._active_data_scope(admin)
        hierarchy = []
        default_scope = None
        selected_state_id = (
            selected_scope.state_id_id if selected_scope else None
        )
        selected_district_id = (
            selected_scope.unique_id
            if selected_scope and selected_scope_type == "district"
            else selected_scope.district_id_id
            if selected_scope
            else None
        )
        if scope:
            if scope.state and (
                not selected_state_id or scope.state_id == selected_state_id
            ):
                hierarchy.append(
                    {"level": "state", "id": scope.state_id, "name": scope.state.name}
                )
            if scope.district and (
                not selected_district_id
                or scope.district_id == selected_district_id
            ):
                hierarchy.append(
                    {
                        "level": "district",
                        "id": scope.district_id,
                        "name": scope.district.name,
                    }
                )
                default_scope = {
                    "scope_type": "district",
                    "scope_id": scope.district_id,
                }
            for level, relation, name_field in (
                ("corporation", "corporations", "corporation_name"),
                ("panchayat_union", "panchayat_unions", "union_name"),
                ("panchayat", "panchayats", "panchayat_name"),
            ):
                entries = [
                    item
                    for item in getattr(scope, relation).all()
                    if (
                        not selected_district_id
                        or item.district_id_id == selected_district_id
                    )
                    and (
                        not selected_scope
                        or selected_scope_type == "district"
                        or (
                            level == selected_scope_type
                            and item.unique_id == selected_scope.unique_id
                        )
                    )
                ]
                hierarchy.extend(
                    {
                        "level": level,
                        "id": item.unique_id,
                        "name": getattr(item, name_field),
                    }
                    for item in entries
                )
                if entries:
                    default_scope = {
                        "scope_type": level,
                        "scope_id": entries[0].unique_id,
                    }
            for ward in scope.wards.all():
                if (
                    selected_district_id
                    and ward.district_id != selected_district_id
                ):
                    continue
                if (
                    selected_scope
                    and selected_scope_type != "district"
                    and getattr(ward, f"{selected_scope_type}_id", None)
                    != selected_scope.unique_id
                ):
                    continue
                hierarchy.append(
                    {
                        "level": "ward",
                        "id": ward.unique_id,
                        "name": ward.ward_name,
                    }
                )
        if selected_scope:
            effective_hierarchy = [
                {
                    "level": "state",
                    "id": selected_scope.state_id_id,
                    "name": selected_scope.state_id.name,
                }
            ]
            if selected_scope_type == "district":
                effective_hierarchy.append(
                    {
                        "level": "district",
                        "id": selected_scope.unique_id,
                        "name": selected_scope.name,
                    }
                )
            else:
                effective_hierarchy.extend(
                    [
                        {
                            "level": "district",
                            "id": selected_scope.district_id_id,
                            "name": selected_scope.district_id.name,
                        },
                        {
                            "level": selected_scope_type,
                            "id": selected_scope.unique_id,
                            "name": getattr(
                                selected_scope,
                                SCOPE_CONFIG[selected_scope_type]["name"],
                            ),
                        },
                    ]
                )
            effective_hierarchy.extend(
                item for item in hierarchy if item["level"] == "ward"
            )
            hierarchy = effective_hierarchy
        return {
            "id": admin.staff_unique_id,
            "name": admin.employee_name,
            "username": admin.username or "",
            "role": admin.governmentusertype_id.get_name_display(),
            "role_level": admin.governmentusertype_id.level,
            "hierarchy": hierarchy,
            "hierarchy_label": " → ".join(item["name"] for item in hierarchy),
            "default_scope": default_scope,
        }

    def _admin_descendant_ids(self, admin):
        descendant_ids = {admin.staff_unique_id}
        frontier = {admin.staff_unique_id}
        while frontier:
            children = set(
                StaffcreationOfficeDetails.objects.filter(
                    staff_head_id__in=frontier,
                    is_deleted=False,
                ).values_list("staff_unique_id", flat=True)
            ) - descendant_ids
            if not children:
                break
            descendant_ids.update(children)
            frontier = children
        return descendant_ids

    def _admin_contains_scope(self, admin, scope_type, selected_scope):
        if not selected_scope:
            return True
        admin_scope = self._active_data_scope(admin)
        if not admin_scope:
            return False
        selected_state_id = selected_scope.state_id_id
        selected_district_id = (
            selected_scope.unique_id
            if scope_type == "district"
            else selected_scope.district_id_id
        )
        if admin_scope.state_id and admin_scope.state_id != selected_state_id:
            return False
        if (
            admin_scope.district_id
            and admin_scope.district_id != selected_district_id
        ):
            return False
        relation = SCOPE_CONFIG[scope_type]["scope_m2m"]
        if relation:
            allowed_ids = set(
                getattr(admin_scope, relation).values_list(
                    "unique_id", flat=True
                )
            )
            if allowed_ids and selected_scope.unique_id not in allowed_ids:
                return False
        return True

    def _date_range(self, request):
        today = timezone.localdate()
        raw_from = request.query_params.get("date_from", "")
        raw_to = request.query_params.get("date_to", "")
        date_from = parse_date(raw_from) if raw_from else today
        date_to = parse_date(raw_to) if raw_to else date_from
        if (raw_from and date_from is None) or (raw_to and date_to is None):
            raise ValidationError({"date": "Dates must use YYYY-MM-DD."})
        if date_from > date_to:
            raise ValidationError({"date": "date_from must be on or before date_to."})
        if date_to - date_from > timedelta(days=366):
            raise ValidationError({"date": "Date range cannot exceed 366 days."})
        return date_from, date_to

    def _scope_queryset(self, request, scope_type, selected_admin=None):
        config = SCOPE_CONFIG[scope_type]
        queryset = _active(config["model"].objects.all()).select_related(
            *config["relations"]
        )
        scope_field_map = {
            "state_id": "state_id",
            "district_id": (
                "unique_id" if scope_type == "district" else "district_id"
            ),
        }
        if scope_type != "district":
            scope_field_map.update(
                {
                    "area_type_id": "area_type_id",
                    f"{config['geo_field']}_id": "unique_id",
                }
            )
        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset,
            request.user,
            field_map=scope_field_map,
        )
        if selected_admin:
            admin_scope = self._active_data_scope(selected_admin)
            if not admin_scope:
                return queryset.none()
            if admin_scope.state_id:
                queryset = queryset.filter(state_id=admin_scope.state_id)
            if admin_scope.district_id:
                if scope_type == "district":
                    queryset = queryset.filter(unique_id=admin_scope.district_id)
                else:
                    queryset = queryset.filter(district_id=admin_scope.district_id)
            scope_relation = config["scope_m2m"]
            if scope_relation:
                allowed_ids = list(
                    getattr(admin_scope, scope_relation).values_list(
                        "unique_id", flat=True
                    )
                )
                if allowed_ids:
                    queryset = queryset.filter(unique_id__in=allowed_ids)
        state_id = request.query_params.get("state_id")
        district_id = request.query_params.get("district_id")
        if state_id:
            queryset = queryset.filter(state_id=state_id)
        if district_id and scope_type != "district":
            queryset = queryset.filter(district_id=district_id)
        elif district_id:
            queryset = queryset.filter(unique_id=district_id)
        return queryset.order_by(config["name"])

    def _selected_scope(self, config, scoped_queryset, scope_id):
        if not scope_id:
            return None
        selected = scoped_queryset.filter(unique_id=scope_id).first()
        if selected:
            return selected
        if config["model"].objects.filter(unique_id=scope_id).exists():
            raise PermissionDenied("The selected scope is outside your access.")
        raise ValidationError({"scope_id": "Unknown scope."})

    def _staff_queryset(self, request, config, scope_id, selected_admin=None):
        queryset = StaffcreationOfficeDetails.objects.select_related(
            "personal_details",
            "state",
            "district",
            "area_type",
            "corporation",
            "panchayat_union",
            "panchayat",
            "staffusertype_id",
            "contractorusertype_id",
            "governmentusertype_id",
            "user_type_id",
        ).prefetch_related(
            "data_scopes__corporations",
            "data_scopes__panchayat_unions",
            "data_scopes__panchayats",
        )
        queryset = filter_staff_queryset_by_requester_scope(queryset, request.user)
        if selected_admin:
            queryset = queryset.filter(
                staff_unique_id__in=self._admin_descendant_ids(selected_admin)
            )
        if scope_id:
            data_scope_lookup = (
                {"data_scopes__district_id": scope_id}
                if config["scope_m2m"] is None
                else {
                    f"data_scopes__{config['scope_m2m']}__unique_id": scope_id
                }
            )
            queryset = queryset.filter(
                Q(**{f"{config['staff_field']}_id": scope_id})
                | Q(
                    **data_scope_lookup,
                    data_scopes__is_active=True,
                    data_scopes__is_deleted=False,
                )
            )
        status_values = set(_multi_values(request.query_params, "status"))
        if not status_values or "all" in status_values or status_values == {
            "active",
            "inactive",
        }:
            pass
        elif status_values == {"active"}:
            queryset = queryset.filter(active_status=True)
        elif status_values == {"inactive"}:
            queryset = queryset.filter(active_status=False)
        else:
            raise ValidationError({
                "status": "Use active and/or inactive."
            })

        role_id = request.query_params.get("role_id")
        if role_id:
            queryset = queryset.filter(
                Q(staffusertype_id=role_id)
                | Q(contractorusertype_id=role_id)
                | Q(governmentusertype_id=role_id)
                | Q(user_type_id=role_id)
            )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(employee_name__icontains=search)
                | Q(emp_id__icontains=search)
                | Q(staff_unique_id__icontains=search)
                | Q(username__icontains=search)
                | Q(office_email__icontains=search)
                | Q(personal_details__contact_mobile__icontains=search)
                | Q(personal_details__contact_email__icontains=search)
            )
        ordering = request.query_params.get("ordering", "employee_name")
        if ordering not in ALLOWED_ORDERING:
            raise ValidationError({"ordering": "Unsupported ordering field."})
        return queryset.distinct().order_by(ordering)

    def _permission_counts(self, staff_queryset):
        staff_ids = list(staff_queryset.values_list("staff_unique_id", flat=True))
        rows = (
            UserScreenPermission.objects.filter(
                staff_id__in=staff_ids,
                is_active=True,
                is_deleted=False,
            )
            .values("staff_id")
            .annotate(
                main_screens=Count("mainscreen_id", distinct=True),
                user_screens=Count("userscreen_id", distinct=True),
                actions=Count("userscreenaction_id", distinct=True),
                last_permission_update=Max("updated_at"),
            )
        )
        return {row["staff_id"]: row for row in rows}

    def _staff_summary(self, staff_queryset, permission_counts):
        staff = list(staff_queryset)
        active_scope_staff_ids = set(
            StaffDataScope.objects.filter(
                staff_id__in=[item.staff_unique_id for item in staff],
                is_active=True,
                is_deleted=False,
            ).values_list("staff_id", flat=True)
        )
        active = sum(1 for item in staff if item.active_status)
        login_enabled = sum(1 for item in staff if item.login_enabled)
        with_permissions = sum(
            1 for item in staff if permission_counts.get(item.staff_unique_id, {}).get("actions", 0)
        )
        fully_configured = sum(
            1
            for item in staff
            if item.active_status
            and item.login_enabled
            and item.staff_unique_id in active_scope_staff_ids
            and permission_counts.get(item.staff_unique_id, {}).get("actions", 0)
        )
        return {
            "total_staff": len(staff),
            "active_staff": active,
            "inactive_staff": len(staff) - active,
            "login_enabled": login_enabled,
            "login_disabled": len(staff) - login_enabled,
            "with_permissions": with_permissions,
            "without_permissions": len(staff) - with_permissions,
            "fully_configured": fully_configured,
            "partially_configured": max(len(staff) - fully_configured, 0),
            "main_screen_permissions": sum(
                row["main_screens"] for row in permission_counts.values()
            ),
            "user_screen_permissions": sum(
                row["user_screens"] for row in permission_counts.values()
            ),
            "action_permissions": sum(row["actions"] for row in permission_counts.values()),
        }

    def _scope_rows(self, request, scope_type, scopes, selected_admin=None):
        config = SCOPE_CONFIG[scope_type]
        rows = []
        for scope in scopes[:250]:
            staff = self._staff_queryset(
                request, config, scope.unique_id, selected_admin
            )
            permission_counts = self._permission_counts(staff)
            summary = self._staff_summary(staff, permission_counts)
            last_update = staff.aggregate(value=Max("updated_at"))["value"]
            rows.append(
                {
                    **self._scope_ref(config, scope),
                    **summary,
                    "distinct_roles": len(
                        {
                            _role_name(item)
                            for item in staff
                            if _role_name(item)
                        }
                    ),
                    "last_updated": last_update.isoformat() if last_update else None,
                }
            )
        return rows

    def _scope_ref(self, config, scope):
        is_district = config["geo_field"] == "district"
        return {
            "id": scope.unique_id,
            "name": getattr(scope, config["name"]),
            "scope_type": next(
                key for key, value in SCOPE_CONFIG.items() if value is config
            ),
            "scope_type_label": config["label"],
            "state_id": scope.state_id_id,
            "state_name": getattr(scope.state_id, "name", ""),
            "district_id": scope.unique_id if is_district else scope.district_id_id,
            "district_name": (
                scope.name if is_district else getattr(scope.district_id, "name", "")
            ),
        }

    def _filters(
        self,
        request,
        selected_scope_type,
        selected_admin=None,
        selected_scope=None,
    ):
        scopes = self._scope_queryset(
            request, selected_scope_type, selected_admin
        )
        states = {}
        districts = {}
        for scope in scopes:
            if scope.state_id:
                states[scope.state_id_id] = scope.state_id.name
            if selected_scope_type == "district":
                districts[scope.unique_id] = scope.name
            elif scope.district_id:
                districts[scope.district_id_id] = scope.district_id.name
        staff = filter_staff_queryset_by_requester_scope(
            StaffcreationOfficeDetails.objects.select_related(
                "staffusertype_id",
                "contractorusertype_id",
                "governmentusertype_id",
                "user_type_id",
            ),
            request.user,
        )
        roles = {}
        for item in staff:
            for field in (
                "staffusertype_id",
                "contractorusertype_id",
                "governmentusertype_id",
                "user_type_id",
            ):
                role = getattr(item, field, None)
                if role:
                    roles[str(role.pk)] = getattr(role, "name", str(role))
        config = SCOPE_CONFIG[selected_scope_type]
        admins = [
            admin
            for admin in self._admin_queryset(request)
            if self._admin_contains_scope(
                admin,
                selected_scope_type,
                selected_scope,
            )
        ]
        return {
            "admins": [
                self._admin_ref(admin) for admin in admins
            ],
            "states": [{"id": key, "name": value} for key, value in sorted(states.items())],
            "districts": [
                {"id": key, "name": value} for key, value in sorted(districts.items())
            ],
            "scope_types": [
                {"id": key, "name": value["label"]}
                for key, value in SCOPE_CONFIG.items()
            ],
            "scopes": [self._scope_ref(config, scope) for scope in scopes],
            "roles": [{"id": key, "name": value} for key, value in sorted(roles.items())],
        }

    def _staff_rows(self, request, staff_queryset, permission_counts):
        try:
            page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)
            page_number = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            raise ValidationError({"pagination": "page and page_size must be integers."})
        paginator = Paginator(staff_queryset, page_size)
        page = paginator.get_page(page_number)
        rows = []
        for item in page.object_list:
            permissions = permission_counts.get(item.staff_unique_id, {})
            hierarchy = self._staff_hierarchy(item)
            rows.append(
                {
                    "staff_id": item.staff_unique_id,
                    "emp_id": item.emp_id,
                    "name": item.employee_name,
                    "username": item.username,
                    "email": item.office_email,
                    "phone": getattr(item.personal_details, "contact_mobile", None)
                    if hasattr(item, "personal_details")
                    else None,
                    "role": _role_name(item),
                    "active": item.active_status,
                    "login_enabled": item.login_enabled,
                    "main_screens": permissions.get("main_screens", 0),
                    "user_screens": permissions.get("user_screens", 0),
                    "actions": permissions.get("actions", 0),
                    **hierarchy,
                }
            )
        return {
            "results": rows,
            "pagination": {
                "count": paginator.count,
                "page": page.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
            },
        }

    def _staff_hierarchy(self, staff):
        active_scopes = [
            scope
            for scope in staff.data_scopes.all()
            if scope.is_active and not scope.is_deleted
        ]
        scope = active_scopes[0] if active_scopes else None

        if scope:
            levels = (
                ("panchayat", scope.panchayats.all(), "panchayat_name"),
                ("panchayat_union", scope.panchayat_unions.all(), "union_name"),
                ("corporation", scope.corporations.all(), "corporation_name"),
            )
            for level, objects, name_field in levels:
                names = [getattr(item, name_field) for item in objects]
                if names:
                    return {
                        "hierarchy_level": level,
                        "hierarchy_level_label": SCOPE_CONFIG[level]["label"],
                        "hierarchy_names": names,
                    }
            if scope.district:
                return {
                    "hierarchy_level": "district",
                    "hierarchy_level_label": "District",
                    "hierarchy_names": [scope.district.name],
                }
            if scope.state:
                return {
                    "hierarchy_level": "state",
                    "hierarchy_level_label": "State",
                    "hierarchy_names": [scope.state.name],
                }

        direct_levels = (
            ("panchayat", staff.panchayat, "panchayat_name"),
            ("panchayat_union", staff.panchayat_union, "union_name"),
            ("corporation", staff.corporation, "corporation_name"),
            ("district", staff.district, "name"),
            ("state", staff.state, "name"),
        )
        for level, obj, name_field in direct_levels:
            if obj:
                return {
                    "hierarchy_level": level,
                    "hierarchy_level_label": (
                        SCOPE_CONFIG[level]["label"]
                        if level in SCOPE_CONFIG
                        else "State"
                    ),
                    "hierarchy_names": [getattr(obj, name_field)],
                }
        return {
            "hierarchy_level": "unassigned",
            "hierarchy_level_label": "Unassigned",
            "hierarchy_names": [],
        }

    def _assignment_payload(
        self, request, config, selected_scope, staff_queryset, date_from, date_to
    ):
        empty = {
            "assignment_kpis": {
                "staff_assigned": 0,
                "staff_unassigned": staff_queryset.count() if selected_scope else 0,
                "trip_assignments": 0,
                "scheduled_trips": 0,
                "in_progress_trips": 0,
                "completed_trips": 0,
                "cancelled_trips": 0,
                "vehicles_total": 0,
                "vehicles_assigned": 0,
                "vehicles_unassigned": 0,
                "teams": 0,
            },
            "assignment_rows": [],
            "vehicle_performance": [],
            "trip_performance": [],
            "team_performance": [],
        }
        if not selected_scope:
            return empty

        geo_field = config["geo_field"]
        trips = DailyTripAssignment.objects.filter(
            is_deleted=False,
            trip_date__range=(date_from, date_to),
            **{f"{geo_field}_id": selected_scope.unique_id},
        ).select_related(
            "trip_plan_id",
            "vehicle_id",
            "vehicle_id__vehicle_type",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__operator_id",
            "alt_staff_template_id",
            "alt_staff_template_id__driver_id",
            "alt_staff_template_id__operator_id",
        ).prefetch_related("wards", "waste_types")
        trips = filter_flat_geo_queryset_by_requester_scope(trips, request.user)

        trip_statuses = set(
            _multi_values(request.query_params, "trip_status")
        )
        if trip_statuses:
            valid_statuses = {
                choice[0] for choice in DailyTripAssignment.STATUS_CHOICES
            }
            invalid_statuses = trip_statuses - valid_statuses
            if invalid_statuses:
                raise ValidationError({"trip_status": "Unsupported trip status."})
            trips = trips.filter(status__in=trip_statuses)
        vehicle_id = request.query_params.get("vehicle_id")
        if vehicle_id:
            trips = trips.filter(vehicle_id=vehicle_id)
        team_id = request.query_params.get("team_id")
        if team_id:
            trips = trips.filter(staff_template_id=team_id)
        ward_id = request.query_params.get("ward_id")
        if ward_id:
            trips = trips.filter(wards__unique_id=ward_id)
        trips = list(trips.distinct().order_by("-trip_date", "-scheduled_time"))

        all_extra_ids = set()
        for trip in trips:
            template = trip.alt_staff_template_id or trip.staff_template_id
            all_extra_ids.update(str(value) for value in (template.extra_operator_id or []))
        extra_staff = {
            staff.staff_unique_id: staff
            for staff in StaffcreationOfficeDetails.objects.filter(
                staff_unique_id__in=all_extra_ids
            )
        }

        attendance_ids = set(
            DailyAttendanceReg.objects.filter(
                recognition_date__range=(date_from, date_to),
                staff_id__in=staff_queryset.values("staff_unique_id"),
            ).values_list("staff_id", flat=True)
        )
        allowed_staff_ids = set(
            staff_queryset.values_list("staff_unique_id", flat=True)
        )
        assignment_rows = []
        assigned_staff_ids = set()
        vehicle_trip_counts = defaultdict(int)
        team_trip_counts = defaultdict(int)
        team_staff_ids = defaultdict(set)

        role_filters = set(
            _multi_values(request.query_params, "assignment_role")
        )
        valid_roles = {"driver", "operator", "additional_operator"}
        if role_filters - valid_roles:
            raise ValidationError({
                "assignment_role": "Unsupported assignment role."
            })
        for trip in trips:
            regular = trip.staff_template_id
            template = trip.alt_staff_template_id or regular
            substituted = trip.alt_staff_template_id is not None
            members = [
                ("driver", template.driver_id),
                ("operator", template.operator_id),
            ]
            members.extend(
                ("additional_operator", extra_staff.get(str(staff_id)))
                for staff_id in (template.extra_operator_id or [])
            )
            for role, staff in members:
                if not staff or staff.staff_unique_id not in allowed_staff_ids:
                    continue
                if role_filters and role not in role_filters:
                    continue
                assigned_staff_ids.add(staff.staff_unique_id)
                team_staff_ids[regular.unique_id].add(staff.staff_unique_id)
                assignment_rows.append(
                    {
                        "staff_id": staff.staff_unique_id,
                        "emp_id": staff.emp_id,
                        "staff_name": staff.employee_name,
                        "assignment_role": role,
                        "staff_active": staff.active_status,
                        "attendance_status": (
                            "Present"
                            if staff.staff_unique_id in attendance_ids
                            else "No punch"
                        ),
                        "team_id": regular.unique_id,
                        "team_code": regular.display_code,
                        "effective_team_code": template.display_code,
                        "is_substitute": substituted,
                        "trip_assignment_id": trip.unique_id,
                        "trip_plan_code": trip.trip_plan_id.display_code,
                        "trip_date": trip.trip_date.isoformat(),
                        "scheduled_time": trip.scheduled_time.isoformat(),
                        "actual_start_time": (
                            trip.actual_start_time.isoformat()
                            if trip.actual_start_time
                            else None
                        ),
                        "actual_end_time": (
                            trip.actual_end_time.isoformat()
                            if trip.actual_end_time
                            else None
                        ),
                        "trip_status": trip.status,
                        "approval_status": trip.approval_status,
                        "vehicle_id": trip.vehicle_id_id,
                        "vehicle_no": (
                            trip.vehicle_id.vehicle_no if trip.vehicle_id else None
                        ),
                        "vehicle_type": (
                            trip.vehicle_id.vehicle_type.vehicleType
                            if trip.vehicle_id and trip.vehicle_id.vehicle_type
                            else None
                        ),
                        "vehicle_capacity": (
                            float(trip.vehicle_id.capacity)
                            if trip.vehicle_id and trip.vehicle_id.capacity is not None
                            else None
                        ),
                        "vehicle_active": (
                            trip.vehicle_id.is_active if trip.vehicle_id else None
                        ),
                        "wards": [ward.ward_name for ward in trip.wards.all()],
                        "waste_types": [
                            getattr(waste_type, "wasteType", str(waste_type))
                            for waste_type in trip.waste_types.all()
                        ],
                    }
                )
            if trip.vehicle_id_id:
                vehicle_trip_counts[trip.vehicle_id_id] += 1
            team_trip_counts[regular.unique_id] += 1

        vehicles = VehicleCreation.objects.filter(
            is_deleted=False,
            **{f"{geo_field}_id": selected_scope.unique_id},
        ).select_related("vehicle_type")
        vehicles = filter_flat_geo_queryset_by_requester_scope(vehicles, request.user)
        vehicle_rows = [
            {
                "vehicle_id": vehicle.unique_id,
                "registration_no": vehicle.vehicle_no,
                "vehicle_type": (
                    vehicle.vehicle_type.vehicleType if vehicle.vehicle_type else ""
                ),
                "capacity": float(vehicle.capacity or 0),
                "trips": vehicle_trip_counts.get(vehicle.unique_id, 0),
                "status": "Active" if vehicle.is_active else "Inactive",
            }
            for vehicle in vehicles
        ]
        trip_rows = [
            {
                "trip_id": trip.unique_id,
                "trip_plan_code": trip.trip_plan_id.display_code,
                "vehicle_no": trip.vehicle_id.vehicle_no if trip.vehicle_id else "",
                "team_code": trip.staff_template_id.display_code,
                "trip_date": trip.trip_date.isoformat(),
                "start_time": trip.scheduled_time.isoformat(),
                "wards": [ward.ward_name for ward in trip.wards.all()],
                "status": trip.status,
            }
            for trip in trips
        ]
        team_rows = [
            {
                "team_id": team_id_value,
                "team_name": next(
                    (
                        trip.staff_template_id.display_code
                        for trip in trips
                        if trip.staff_template_id_id == team_id_value
                    ),
                    team_id_value,
                ),
                "staff_count": len(team_staff_ids[team_id_value]),
                "trips": trip_count,
            }
            for team_id_value, trip_count in team_trip_counts.items()
        ]
        status_counts = defaultdict(int)
        for trip in trips:
            status_counts[trip.status] += 1
        assigned_vehicle_ids = set(vehicle_trip_counts)
        return {
            "assignment_kpis": {
                "staff_assigned": len(assigned_staff_ids),
                "staff_unassigned": max(staff_queryset.count() - len(assigned_staff_ids), 0),
                "trip_assignments": len(trips),
                "scheduled_trips": status_counts["Scheduled"],
                "in_progress_trips": status_counts["In Progress"],
                "completed_trips": status_counts["Completed"],
                "cancelled_trips": status_counts["Cancelled"],
                "vehicles_total": vehicles.count(),
                "vehicles_assigned": len(assigned_vehicle_ids),
                "vehicles_unassigned": max(vehicles.count() - len(assigned_vehicle_ids), 0),
                "teams": len(team_trip_counts),
            },
            "assignment_rows": assignment_rows[:500],
            "vehicle_performance": vehicle_rows,
            "trip_performance": trip_rows,
            "team_performance": team_rows,
        }
