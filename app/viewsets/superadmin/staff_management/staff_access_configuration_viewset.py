from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope
from app.serializers.superadmin.staff_management.staff_access_configuration_serializer import (
    StaffAccessConfigurationSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.hierarchy import filter_staff_queryset_by_requester_scope


class StaffAccessConfigurationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "staff_access_configuration"
    queryset = Staffcreation.objects.select_related(
        "personal_details",
        "department_id",
        "designation_id",
        "staffusertype_id",
        "contractorusertype_id",
        "governmentusertype_id",
    ).all()
    serializer_class = StaffAccessConfigurationSerializer
    lookup_field = "staff_unique_id"
    permission_resource = "StaffAccessConfiguration"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["employee_name", "staff_unique_id", "department", "designation"]
    ordering_fields = ["employee_name", "staff_unique_id", "doj"]

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staff-access-configuration"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        staff = result["staff"]
        self.log_audit(
            request,
            instance=staff,
            previous_data=None,
            new_data=self._serialize_instance(staff),
        )
        return Response(
            serializer.to_representation(result),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        previous_data = self._serialize_instance(instance)
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        staff = result["staff"]
        self.log_audit(
            request,
            instance=staff,
            previous_data=previous_data,
            new_data=self._serialize_instance(staff),
        )
        return Response(serializer.to_representation(result))

    @action(detail=False, methods=["get"], url_path="app-modules")
    def app_modules(self, request):
        """The App Module master, for the tick list on this form.

        Ticking a module decides whether the person may sign into that app at
        all. What they can do inside comes from the ordinary screen
        permissions, which are the same rows that govern web.
        """
        from app.models.superadmin.screen_management.app_module import AppModule

        modules = AppModule.objects.filter(is_active=True, is_deleted=False)
        return Response([
            {
                "uniqueId": m.unique_id,
                "moduleKey": m.module_key,
                "surfaceKey": m.surface_key,
                "label": m.label,
                "route": m.route,
                "orderNo": m.order_no,
                "description": m.description,
            }
            for m in modules
        ])

    @action(detail=False, methods=["get", "post"], url_path="staff-app-modules")
    def staff_app_modules(self, request):
        """Read or set the App Modules ticked for one staff member.

        Kept as its own action rather than folded into this form's main save:
        that payload is written by the existing serializer against
        UserScreenPermission/StaffDataScope, and app-module access lives on the
        separate StaffAccessConfiguration. Mixing them would mean rewriting a
        working save path to carry one extra list.

        GET  ?staff_id=STC-...            -> {"app_module_ids": [...]}
        POST {"staff_id", "app_module_ids"} -> replaces the ticks
        """
        from django.core.cache import cache

        from app.models.superadmin.screen_management.app_module import AppModule
        from app.models.superadmin.staff_management.staff_access_configuration import (
            StaffAccessConfiguration,
        )
        from app.models.superadmin.staff_management.staffcreation import (
            StaffcreationOfficeDetails,
        )

        staff_id = (
            request.data.get("staff_id")
            if request.method == "POST"
            else request.query_params.get("staff_id")
        )
        if not staff_id:
            return Response(
                {"staff_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff = StaffcreationOfficeDetails.objects.filter(
            staff_unique_id=staff_id, is_deleted=False
        ).first()
        if not staff:
            return Response(
                {"staff_id": f"No staff member '{staff_id}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        config = StaffAccessConfiguration.objects.filter(
            staff_id_id=staff_id, is_deleted=False
        ).first()

        if request.method == "GET":
            return Response({
                "staff_id": staff_id,
                "app_module_ids": (
                    [m.unique_id for m in config.app_modules.filter(is_deleted=False)]
                    if config else []
                ),
                "app_module": staff.app_module,
            })

        module_ids = request.data.get("app_module_ids") or []
        if config is None:
            config = StaffAccessConfiguration.objects.create(staff_id=staff)
        config.app_modules.set(
            AppModule.objects.filter(unique_id__in=module_ids, is_deleted=False)
        )

        # Keep the landing app in step: if the person was given exactly one
        # module and has no landing set, that module is unambiguously it.
        surfaces = list(
            config.app_modules.filter(is_deleted=False).values_list(
                "surface_key", flat=True
            )
        )
        if len(surfaces) == 1 and not staff.app_module:
            StaffcreationOfficeDetails.objects.filter(pk=staff.pk).update(
                app_module=surfaces[0]
            )

        cache.clear()
        return Response({"staff_id": staff_id, "app_module_ids": module_ids})

    @action(detail=False, methods=["get"], url_path="role-template")
    def role_template(self, request):
        """The screens a given app role actually calls.

        Backs the "Apply defaults" button. Every one of these is an ordinary
        screen permission an admin could tick by hand — this only saves them
        knowing which ones the Driver app happens to read.
        """
        from app.models.superadmin.screen_management.userscreen import UserScreen
        from app.models.superadmin.screen_management.userscreenaction import (
            UserScreenAction,
        )
        from app.utils.app_feature_grants import ROLE_SCREEN_TEMPLATES

        role = (request.query_params.get("role") or "").strip().lower()
        template = ROLE_SCREEN_TEMPLATES.get(role)
        if template is None:
            return Response(
                {
                    "detail": f"No template for '{role}'.",
                    "available": sorted(ROLE_SCREEN_TEMPLATES),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        wanted = {}
        for screens in template.values():
            for name, actions in screens.items():
                wanted.setdefault(name, set()).update(actions)

        action_rows = {
            (row.variable_name or row.action_name or "").lower(): row
            for row in UserScreenAction.objects.filter(is_deleted=False)
        }

        screens = []
        for row in UserScreen.objects.filter(
            userscreen_name__in=wanted, is_deleted=False
        ).select_related("mainscreen_id"):
            screens.append({
                "userScreenId": row.unique_id,
                "userScreenName": row.userscreen_name,
                "mainScreenId": row.mainscreen_id_id,
                "mainScreenName": row.mainscreen_id.mainscreen_name,
                "actions": [
                    {"actionId": action_rows[a].unique_id, "actionName": a}
                    for a in sorted(wanted[row.userscreen_name])
                    if a in action_rows
                ],
            })

        return Response({"role": role, "screens": screens})

    @action(detail=False, methods=["get"], url_path="scope-admins")
    def scope_admins(self, request):
        """Admins the caller may place above a new staff account."""
        queryset = Staffcreation.objects.select_related(
            "governmentusertype_id",
        ).filter(
            active_status=True,
            login_enabled=True,
            is_deleted=False,
            governmentusertype_id__name__endswith="_admin",
        )
        if not getattr(request.user, "is_superuser", False):
            scoped_ids = filter_staff_queryset_by_requester_scope(
                queryset,
                request.user,
            ).values_list("staff_unique_id", flat=True)
            requester_id = getattr(request.user, "staff_unique_id", None)
            if not requester_id:
                requester_id = getattr(
                    getattr(request.user, "staff", None),
                    "staff_unique_id",
                    None,
                )
            requester_filter = Q(staff_unique_id=requester_id) if requester_id else Q(pk__in=[])
            queryset = queryset.filter(
                requester_filter | Q(staff_unique_id__in=scoped_ids)
            )

        scopes = {
            scope.staff_id: scope
            for scope in StaffDataScope.objects.filter(
                staff_id__in=queryset.values_list("staff_unique_id", flat=True),
                is_active=True,
                is_deleted=False,
            )
            .select_related("state", "district", "area_type")
            .prefetch_related(
                "corporations",
                "municipalities",
                "town_panchayats",
                "panchayat_unions",
                "panchayats",
                "wards",
            )
        }
        results = []
        body_fields = (
            ("corporation_id", "corporations", "corporation_name", "Corporation"),
            ("municipality_id", "municipalities", "municipality_name", "Municipality"),
            ("town_panchayat_id", "town_panchayats", "town_panchayat_name", "Town Panchayat"),
            ("panchayat_union_id", "panchayat_unions", "union_name", "Panchayat Union"),
            ("panchayat_id", "panchayats", "panchayat_name", "Panchayat"),
        )
        for admin in queryset.order_by("employee_name"):
            scope = scopes.get(admin.staff_unique_id)
            if not scope:
                continue
            hierarchy = []
            if scope.state:
                hierarchy.append({"level": "state", "id": scope.state_id, "name": scope.state.name})
            if scope.district:
                hierarchy.append({"level": "district", "id": scope.district_id, "name": scope.district.name})
            local_bodies = {}
            for key, relation, name_field, label in body_fields:
                entries = [
                    {"id": item.unique_id, "name": getattr(item, name_field), "level": key}
                    for item in getattr(scope, relation).all()
                ]
                local_bodies[key] = entries
                hierarchy.extend(
                    {"level": key, "id": entry["id"], "name": entry["name"], "label": label}
                    for entry in entries
                )
            ward_entries = [
                {"id": ward.unique_id, "name": ward.ward_name}
                for ward in scope.wards.all()
            ]
            hierarchy.extend(
                {"level": "ward", "id": ward["id"], "name": ward["name"], "label": "Ward"}
                for ward in ward_entries
            )
            results.append({
                "id": admin.staff_unique_id,
                "name": admin.employee_name,
                "username": admin.username or "",
                "role": admin.governmentusertype_id.get_name_display(),
                "roleLevel": admin.governmentusertype_id.level,
                "scope": {
                    "stateId": scope.state_id,
                    "districtId": scope.district_id,
                    "areaTypeId": scope.area_type_id,
                    "localBodies": local_bodies,
                    "wards": ward_entries,
                },
                "hierarchy": hierarchy,
            })
        return Response(results)

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            transaction.set_rollback(True)

        return Response(
            {
                "valid": True,
                "summary": {
                    "basicInfo": serializer.validated_data.get("basicInfo", {}),
                    "loginConfig": {
                        key: value
                        for key, value in serializer.validated_data.get("loginConfig", {}).items()
                        if key != "password"
                    },
                    "permissions": len(serializer.validated_data.get("permissions") or []),
                    "dashboardPermissions": len(
                        serializer.validated_data.get("dashboardPermissions") or []
                    ),
                    "dataScope": bool(result.get("data_scope")),
                },
            },
            status=status.HTTP_200_OK,
        )
