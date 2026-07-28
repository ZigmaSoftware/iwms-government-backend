from django.core.cache import cache
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from collections import defaultdict
from app.models.superadmin.screen_management.userscreen import UserScreen
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.models.superadmin.screen_management.companyuserscreenpermission import UserScreenPermission
from app.models.superadmin.screen_management.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
from app.serializers.superadmin.screen_management.companyuserscreenpermission_serializer import (
    UserScreenPermissionMultiScreenSerializer,
    UserScreenPermissionSerializer,
)
from app.serializers.superadmin.screen_management.companyuserscreencolumnpermission_serializer import (
    CompanyUserScreenColumnPermissionSerializer,
)

from app.utils.audit_mixin import AuditViewSetMixin


class UserScreenPermissionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = UserScreenPermissionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "screen-managements"
    AUDIT_ENDPOINT = "user-screen-permissions"

    permission_resource = "userscreenpermissions"

    # Makes newest records appear first on page 1
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at", "-created_at"]

    def get_serializer_class(self):
        if getattr(self, "action", None) == "create":
            return UserScreenPermissionMultiScreenSerializer
        return super().get_serializer_class()

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _normalize_permission_payloads(self, payload):
        if "permissions" not in payload:
            return [payload]

        normalized = []
        for permission in payload.get("permissions", []):
            normalized.append({
                "stateId": payload.get("stateId") or payload.get("state_id"),
                "districtId": payload.get("districtId") or payload.get("district_id"),
                "areaTypeId": payload.get("areaTypeId") or payload.get("area_type_id"),
                "localBodyType": payload.get("localBodyType") or payload.get("local_body_type"),
                "localBodyId": payload.get("localBodyId") or payload.get("local_body_id"),
                "permissionType": payload.get("permissionType") or payload.get("permission_type"),
                "mainScreenId": permission.get("mainScreenId") or permission.get("mainscreen_id"),
                "userScreens": permission.get("userScreens") or permission.get("screens") or [],
                "description": payload.get("description", ""),
            })
        return normalized

    def _local_body_from_request(self, request, *, default_local_body_type=None, default_local_body_id=None):
        local_body_type = (
            default_local_body_type
            or request.query_params.get("local_body_type")
            or request.query_params.get("localBodyType")
            or request.data.get("local_body_type")
            or request.data.get("localBodyType")
        )
        local_body_id = (
            default_local_body_id
            or request.query_params.get("local_body_id")
            or request.query_params.get("localBodyId")
            or request.data.get("local_body_id")
            or request.data.get("localBodyId")
        )
        state_id = (
            request.query_params.get("state_id")
            or request.query_params.get("stateId")
            or request.data.get("state_id")
            or request.data.get("stateId")
        )
        district_id = (
            request.query_params.get("district_id")
            or request.query_params.get("districtId")
            or request.data.get("district_id")
            or request.data.get("districtId")
        )
        area_type_id = (
            request.query_params.get("area_type_id")
            or request.query_params.get("areaTypeId")
            or request.data.get("area_type_id")
            or request.data.get("areaTypeId")
        )
        permission_type = (
            request.query_params.get("permission_type")
            or request.query_params.get("permissionType")
            or request.data.get("permission_type")
            or request.data.get("permissionType")
        )
        return {
            "local_body_type": local_body_type,
            "local_body_id": local_body_id,
            "state_id": state_id,
            "district_id": district_id,
            "area_type_id": area_type_id,
            "permission_type": permission_type,
        }

    def _local_body_filter_kwargs(self, scope, *, permission_owner_kind="super_admin"):
        filters = {
            "local_body_type": scope["local_body_type"],
            "local_body_id": scope["local_body_id"],
        }
        if scope.get("state_id"):
            filters["state_id_id"] = scope["state_id"]
        if scope.get("district_id"):
            filters["district_id_id"] = scope["district_id"]
        if scope.get("area_type_id"):
            filters["area_type_id_id"] = scope["area_type_id"]
        if scope.get("permission_type"):
            filters["permission_type"] = scope["permission_type"]
        if permission_owner_kind:
            filters["permission_owner_kind"] = permission_owner_kind
        return filters

    def _sync_nested_permissions(self, request, update_only=False):
        payloads = self._normalize_permission_payloads(request.data)
        results = []

        with transaction.atomic():
            for payload in payloads:
                serializer = UserScreenPermissionMultiScreenSerializer(
                    data=payload,
                    context={"update_only": update_only},
                )
                serializer.is_valid(raise_exception=True)
                results.append(serializer.save())

        cache.clear()

        return Response(
            {
                "message": "Permissions saved successfully",
                "results": [
                    {
                        "created": len(result["created"]),
                        "updated": len(result["updated"]),
                        "deleted": len(result["deleted"]),
                        "created_columns": len(result["created_columns"]),
                        "updated_columns": len(result["updated_columns"]),
                        "deleted_columns": len(result["deleted_columns"]),
                    }
                    for result in results
                ],
            },
            status=status.HTTP_200_OK,
        )

    def _sync_permissions(
        self,
        request,
        update_only=False,
        local_body_type=None,
        local_body_id=None,
    ):
        scope = self._local_body_from_request(
            request,
            default_local_body_type=local_body_type,
            default_local_body_id=local_body_id,
        )
        if not scope["local_body_type"] or not scope["local_body_id"]:
            return Response(
                {"error": "local_body_type and local_body_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.copy()
        payload["localBodyType"] = scope["local_body_type"]
        payload["localBodyId"] = scope["local_body_id"]
        payload["stateId"] = scope.get("state_id")
        payload["districtId"] = scope.get("district_id")
        payload["areaTypeId"] = scope.get("area_type_id")

        with transaction.atomic():
            serializer = UserScreenPermissionMultiScreenSerializer(
                data=payload,
                context={"update_only": update_only},
            )
            serializer.is_valid(raise_exception=True)
            result = serializer.save()

        cache.clear()

        return Response(
            {
                "created": UserScreenPermissionSerializer(result["created"], many=True).data,
                "updated": UserScreenPermissionSerializer(result["updated"], many=True).data,
                "deleted": UserScreenPermissionSerializer(result["deleted"], many=True).data,
                "created_columns": CompanyUserScreenColumnPermissionSerializer(result.get("created_columns", []), many=True).data,
                "updated_columns": CompanyUserScreenColumnPermissionSerializer(result.get("updated_columns", []), many=True).data,
                "deleted_columns": CompanyUserScreenColumnPermissionSerializer(result.get("deleted_columns", []), many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Queryset
    # ---------------------------------------------------------
    def get_queryset(self):
        queryset = UserScreenPermission.objects.filter(is_deleted=False).select_related(
            "usertype_id",
            "staffusertype_id",
            "contractorusertype_id",
            "governmentusertype_id",
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id",
        )

        request = getattr(self, "request", None)
        if request is not None and getattr(self, "action", None) == "list":
            scope = self._local_body_from_request(request)
            if scope["local_body_type"] and scope["local_body_id"]:
                # Super Admin's list shows the Local Body's own baseline
                # grants only — per-staff rows (permission_owner_kind="staff",
                # written by Staff Access Configuration) live in the same
                # table but are a separate, independently-managed row set.
                queryset = queryset.filter(**self._local_body_filter_kwargs(scope))

        return queryset

    @swagger_auto_schema(responses={200: UserScreenPermissionSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=UserScreenPermissionMultiScreenSerializer,
        responses={200: "Permissions saved successfully", 201: UserScreenPermissionSerializer},
    )
    def create(self, request, *args, **kwargs):
        if "permissions" in request.data or "userScreens" in request.data or "screens" in request.data:
            return self._sync_nested_permissions(request, update_only=False)

        serializer = UserScreenPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    # ---------------------------------------------------------
    # Retrieve
    # ---------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    # ---------------------------------------------------------
    # Bulk Sync / Update (Local Body ownership)
    # ---------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path=r"bulk-sync-multi-localbody/(?P<local_body_type>[^/]+)/(?P<local_body_id>[^/.]+)",
    )
    def bulk_sync_multi_localbody(self, request, local_body_type, local_body_id):
        return self._sync_permissions(
            request,
            local_body_type=local_body_type,
            local_body_id=local_body_id,
            update_only=False,
        )

    @action(
        detail=False,
        methods=["post", "put"],
        url_path=r"update-by-localbody/(?P<local_body_type>[^/]+)/(?P<local_body_id>[^/.]+)",
    )
    def update_by_localbody(self, request, local_body_type, local_body_id):
        return self._sync_permissions(
            request,
            local_body_type=local_body_type,
            local_body_id=local_body_id,
            update_only=True,
        )

    # ---------------------------------------------------------
    # By Staff + Mainscreen (Shows ALL screens with their actions)
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="by-staff-format")
    def by_staff_format(self, request):
        return self._by_user_format(request)

    @action(detail=False, methods=["get"], url_path="by-user-format")
    def by_user_format(self, request):
        return self._by_user_format(request)

    def _by_user_format(self, request):
        scope = self._local_body_from_request(request)
        mainscreen_id = request.query_params.get("mainscreen_id")

        if not scope["local_body_type"] or not scope["local_body_id"] or not mainscreen_id:
            return Response(
                {"error": "local_body_type, local_body_id and mainscreen_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔥 CACHE KEY
        permission_type_key = scope.get("permission_type") or "screen"
        cache_key = (
            f"perm_global_localbody_{scope['local_body_type']}_{scope['local_body_id']}"
            f"_{mainscreen_id}_{permission_type_key}"
        )
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        local_body_filters = self._local_body_filter_kwargs(scope)
        # CompanyUserScreenColumnPermission has no permission_type column — it
        # IS the field-permission data, so this filter only applies to the
        # UserScreenPermission (screen/action) queryset.
        column_local_body_filters = {k: v for k, v in local_body_filters.items() if k != "permission_type"}

        # 🔥 OPTIMIZED QUERY (NO MODEL LOAD)
        perms = UserScreenPermission.objects.filter(
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
            **local_body_filters,
        ).values(
            "unique_id",
            "userscreen_id_id",
            "userscreenaction_id_id",
            "description",
        )

        column_perms = CompanyUserScreenColumnPermission.objects.filter(
            userscreen_id__mainscreen_id_id=mainscreen_id,
            is_deleted=False,
            **column_local_body_filters,
        ).values(
            "userscreen_id_id",
            "column_id_id",
            "field_permission_state",
        )

        # 🔥 FAST MAP BUILD
        screen_map = defaultdict(lambda: {"actions": [], "columns": []})
        column_map = defaultdict(list)
        description = ""

        for p in perms:
            screen_map[p["userscreen_id_id"]]["actions"].append(p["userscreenaction_id_id"])

            if not description:
                description = p["description"]

        # Build column permissions map
        for cp in column_perms:
            column_map[cp["userscreen_id_id"]].append({
                "column_id": cp["column_id_id"],
                "can_view": cp["field_permission_state"] != CompanyUserScreenColumnPermission.HIDDEN,
            })

        # 🔥 LIGHTWEIGHT QUERY
        screens_qs = UserScreen.objects.filter(
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
        ).values(
            "unique_id",
            "userscreen_name",
            "folder_name",
            "icon_name",
        )

        # 🔥 FAST RESPONSE BUILD
        screens = [
            {
                "userscreen_id": s["unique_id"],
                "userscreen_name": s["userscreen_name"],
                "folder_name": s["folder_name"],
                "icon_name": s["icon_name"],
                "actionIds": screen_map[s["unique_id"]]["actions"] if s["unique_id"] in screen_map else [],
                "columnIds": [col["column_id"] for col in column_map.get(s["unique_id"], [])],
                "columnPermissions": column_map.get(s["unique_id"], []),
                "has_permissions": s["unique_id"] in screen_map,
            }
            for s in screens_qs
        ]

        response_data = {
            "local_body_type": scope["local_body_type"],
            "local_body_id": scope["local_body_id"],
            "mainscreen_id": mainscreen_id,
            "screens": screens,
            "description": description,
        }

        # 🔥 CACHE SAVE (5 min)
        cache.set(cache_key, response_data, timeout=300)

        return Response(response_data)

    # ---------------------------------------------------------
    # All Screens By Staff (across all mainscreens)
    # ---------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="all-screens-by-staff")
    def all_screens_by_staff(self, request):
        return self._all_screens_by_user(request)

    @action(detail=False, methods=["get"], url_path="all-screens-by-user")
    def all_screens_by_user(self, request):
        return self._all_screens_by_user(request)

    def _all_screens_by_user(self, request):
        """
        Get ALL screens assigned to a Local Body across all mainscreens.
        Grouped by mainscreen for better visibility.

        Query params:
        - local_body_type / local_body_id: required
        - state_id / district_id / area_type_id: optional, narrows scope further
        """
        scope = self._local_body_from_request(request)
        if not scope["local_body_type"] or not scope["local_body_id"]:
            return Response(
                {"error": "local_body_type and local_body_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        local_body_filters = self._local_body_filter_kwargs(scope)

        # Get ALL permissions for this Local Body (no mainscreen filter)
        qs = UserScreenPermission.objects.filter(
            is_deleted=False,
            **local_body_filters,
        ).select_related("mainscreen_id")

        if not qs.exists():
            return Response(
                {
                    "local_body_type": scope["local_body_type"],
                    "local_body_id": scope["local_body_id"],
                    "mainscreens": [],
                    "total_screens": 0,
                },
                status=status.HTTP_200_OK,
            )

        # Group by mainscreen
        mainscreen_map = {}

        for perm in qs:
            mainscreen_id = perm.mainscreen_id_id
            mainscreen_name = perm.mainscreen_id.mainscreen_name if perm.mainscreen_id else "Unknown"

            if mainscreen_id not in mainscreen_map:
                mainscreen_map[mainscreen_id] = {
                    "mainscreen_id": mainscreen_id,
                    "mainscreen_name": mainscreen_name,
                    "screens": {},
                }

            scr_id = perm.userscreen_id_id
            act_id = perm.userscreenaction_id_id

            if scr_id not in mainscreen_map[mainscreen_id]["screens"]:
                mainscreen_map[mainscreen_id]["screens"][scr_id] = {
                    "userscreen_id": scr_id,
                    "actions": [],
                }

            mainscreen_map[mainscreen_id]["screens"][scr_id]["actions"].append(act_id)

        # Convert to final format
        mainscreens = []
        total_screens = 0
        for mainscreen_data in mainscreen_map.values():
            screens_list = list(mainscreen_data["screens"].values())
            mainscreen_data["screens"] = screens_list
            total_screens += len(screens_list)
            mainscreens.append(mainscreen_data)

        return Response(
            {
                "local_body_type": scope["local_body_type"],
                "local_body_id": scope["local_body_id"],
                "mainscreens": mainscreens,
                "total_screens": total_screens,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Delete By Local Body + Mainscreen (safe delete)
    # ---------------------------------------------------------
    @action(
        detail=False,
        methods=["delete"],
        url_path=r"delete-by-localbody/(?P<local_body_type>[^/]+)/(?P<local_body_id>[^/.]+)/?",
    )
    def delete_by_localbody(self, request, local_body_type, local_body_id):
        return self._delete_by_local_body(request, local_body_type=local_body_type, local_body_id=local_body_id)

    def _delete_by_local_body(self, request, local_body_type=None, local_body_id=None):
        mainscreen_id = request.query_params.get("mainscreen_id")
        if not mainscreen_id:
            return Response(
                {"error": "mainscreen_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scope = self._local_body_from_request(
            request,
            default_local_body_type=local_body_type,
            default_local_body_id=local_body_id,
        )
        local_body_filters = self._local_body_filter_kwargs(scope)
        column_local_body_filters = {k: v for k, v in local_body_filters.items() if k != "permission_type"}

        qs = UserScreenPermission.objects.filter(
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
            **local_body_filters,
        )

        deleted_count = qs.count()
        if deleted_count > 0:
            qs.update(is_deleted=True, is_active=False)
            CompanyUserScreenColumnPermission.objects.filter(
                userscreen_id__mainscreen_id_id=mainscreen_id,
                is_deleted=False,
                **column_local_body_filters,
            ).update(is_deleted=True, is_active=False)

        return Response(
            {
                "message": "Permissions deleted successfully",
                "deleted_count": deleted_count,
                "local_body_type": scope["local_body_type"],
                "local_body_id": scope["local_body_id"],
                "mainscreen_id": mainscreen_id,
            },
            status=status.HTTP_200_OK,
        )


CompanyUserScreenPermissionViewSet = UserScreenPermissionViewSet
