from django.core.cache import cache
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from collections import defaultdict
from app.models.screen_managements.userscreen import UserScreen
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.models.screen_managements.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
from app.serializers.screen_managements.companyuserscreenpermission_serializer import (
    UserScreenPermissionMultiScreenSerializer,
    UserScreenPermissionSerializer,
)
from app.serializers.screen_managements.companyuserscreencolumnpermission_serializer import (
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
                "userTypeId": (
                    payload.get("userTypeId")
                    or payload.get("usertypeId")
                    or payload.get("usertype_id")
                ),
                "staffUserTypeId": (
                    payload.get("staffUserTypeId")
                    or payload.get("staffusertype_id")
                ),
                "contractorUserTypeId": (
                    payload.get("contractorUserTypeId")
                    or payload.get("contractorusertype_id")
                ),
                "governmentUserTypeId": (
                    payload.get("governmentUserTypeId")
                    or payload.get("governmentusertype_id")
                ),
                "mainScreenId": permission.get("mainScreenId") or permission.get("mainscreen_id"),
                "userScreens": permission.get("userScreens") or permission.get("screens") or [],
                "description": payload.get("description", ""),
            })
        return normalized

    def _role_from_request(self, request, *, default_staffusertype_id=None, default_contractorusertype_id=None, default_governmentusertype_id=None):
        permission_for = (request.query_params.get("permission_for") or request.data.get("permission_for") or "").lower()
        contractorusertype_id = (
            default_contractorusertype_id
            or request.query_params.get("contractorusertype_id")
            or request.query_params.get("contractorUserTypeId")
            or request.data.get("contractorusertype_id")
            or request.data.get("contractorUserTypeId")
        )
        staffusertype_id = (
            default_staffusertype_id
            or request.query_params.get("staffusertype_id")
            or request.query_params.get("staffUserTypeId")
            or request.data.get("staffusertype_id")
            or request.data.get("staffUserTypeId")
        )
        governmentusertype_id = (
            default_governmentusertype_id
            or request.query_params.get("governmentusertype_id")
            or request.query_params.get("governmentUserTypeId")
            or request.data.get("governmentusertype_id")
            or request.data.get("governmentUserTypeId")
        )

        if not contractorusertype_id and staffusertype_id:
            if str(staffusertype_id).startswith("CNTUSRTYPE-") or ContractorUserType.objects.filter(
                unique_id=staffusertype_id,
                is_deleted=False,
            ).exists():
                contractorusertype_id = staffusertype_id
                staffusertype_id = None
        if not governmentusertype_id and staffusertype_id:
            if str(staffusertype_id).startswith("GOVTUSRTYPE-") or GovernmentStaffUserType.objects.filter(
                unique_id=staffusertype_id,
                is_deleted=False,
            ).exists():
                governmentusertype_id = staffusertype_id
                staffusertype_id = None

        if permission_for == "government" or governmentusertype_id:
            return "government", governmentusertype_id
        if permission_for == "contractor" or contractorusertype_id:
            return "contractor", contractorusertype_id
        return "staff", staffusertype_id

    def _role_filter_kwargs(self, permission_for, role_id):
        if permission_for == "government":
            return {"governmentusertype_id_id": role_id}
        if permission_for == "contractor":
            return {"contractorusertype_id_id": role_id}
        return {"staffusertype_id_id": role_id}

    def _role_response_key(self, permission_for):
        if permission_for == "government":
            return "governmentusertype_id"
        return "contractorusertype_id" if permission_for == "contractor" else "staffusertype_id"

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
        staffusertype_id=None,
        update_only=False,
        contractorusertype_id=None,
        governmentusertype_id=None,
    ):
        permission_for, role_id = self._role_from_request(
            request,
            default_staffusertype_id=staffusertype_id,
            default_contractorusertype_id=contractorusertype_id,
            default_governmentusertype_id=governmentusertype_id,
        )
        if not role_id:
            return Response(
                {"error": f"{self._role_response_key(permission_for)} is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.copy()
        if permission_for == "contractor":
            payload["contractorusertype_id"] = role_id
            payload["staffusertype_id"] = None
            payload["governmentusertype_id"] = None
        elif permission_for == "government":
            payload["governmentusertype_id"] = role_id
            payload["staffusertype_id"] = None
            payload["contractorusertype_id"] = None
        else:
            payload["staffusertype_id"] = role_id
            payload["contractorusertype_id"] = None
            payload["governmentusertype_id"] = None

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
        return UserScreenPermission.objects.filter(is_deleted=False).select_related(
            "usertype_id",
            "staffusertype_id",
            "contractorusertype_id",
            "governmentusertype_id",
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id",
        )

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
    # Bulk Sync / Update
    # ---------------------------------------------------------
    @action(detail=False, methods=["post"], url_path=r"bulk-sync-multi/(?P<staffusertype_id>[^/.]+)")
    def bulk_sync_multi(self, request, staffusertype_id):
        return self._sync_permissions(request, staffusertype_id, update_only=False)

    @action(detail=False, methods=["post"], url_path=r"bulk-sync-multi-contractor/(?P<contractorusertype_id>[^/.]+)")
    def bulk_sync_multi_contractor(self, request, contractorusertype_id):
        return self._sync_permissions(
            request,
            contractorusertype_id=contractorusertype_id,
            update_only=False,
        )

    @action(detail=False, methods=["post"], url_path=r"bulk-sync-multi-government/(?P<governmentusertype_id>[^/.]+)")
    def bulk_sync_multi_government(self, request, governmentusertype_id):
        return self._sync_permissions(
            request,
            governmentusertype_id=governmentusertype_id,
            update_only=False,
        )

    @action(detail=False, methods=["post", "put"], url_path=r"update-by-staffusertype/(?P<staffusertype_id>[^/.]+)")
    def update_by_staffusertype(self, request, staffusertype_id):
        return self._sync_permissions(request, staffusertype_id, update_only=False)

    @action(detail=False, methods=["post", "put"], url_path=r"update-by-contractorusertype/(?P<contractorusertype_id>[^/.]+)")
    def update_by_contractorusertype(self, request, contractorusertype_id):
        return self._sync_permissions(
            request,
            contractorusertype_id=contractorusertype_id,
            update_only=True,
        )

    @action(detail=False, methods=["post", "put"], url_path=r"update-by-governmentusertype/(?P<governmentusertype_id>[^/.]+)")
    def update_by_governmentusertype(self, request, governmentusertype_id):
        return self._sync_permissions(
            request,
            governmentusertype_id=governmentusertype_id,
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
        permission_for, role_id = self._role_from_request(request)
        mainscreen_id = request.query_params.get("mainscreen_id")

        if not role_id or not mainscreen_id:
            return Response(
                {"error": f"{self._role_response_key(permission_for)} and mainscreen_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 🔥 CACHE KEY
        cache_key = f"perm_global_{permission_for}_{role_id}_{mainscreen_id}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        role_filters = self._role_filter_kwargs(permission_for, role_id)

        # 🔥 OPTIMIZED QUERY (NO MODEL LOAD)
        perms = UserScreenPermission.objects.filter(
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
            **role_filters,
        ).values(
            "unique_id",
            "userscreen_id_id",
            "userscreenaction_id_id",
            "usertype_id_id",
            "description",
        )

        column_perms = CompanyUserScreenColumnPermission.objects.filter(
            userscreen_id__mainscreen_id_id=mainscreen_id,
            is_deleted=False,
            **role_filters,
        ).values(
            "userscreen_id_id",
            "column_id_id",
            "can_view",
        )

        # 🔥 FAST MAP BUILD
        screen_map = defaultdict(lambda: {"actions": [], "columns": []})
        column_map = defaultdict(list)
        usertype_id = None
        description = ""

        for p in perms:
            screen_map[p["userscreen_id_id"]]["actions"].append(p["userscreenaction_id_id"])

            if not usertype_id:
                usertype_id = p["usertype_id_id"]

            if not description:
                description = p["description"]

        # Build column permissions map
        for cp in column_perms:
            column_map[cp["userscreen_id_id"]].append({
                "column_id": cp["column_id_id"],
                "can_view": cp["can_view"],
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
            self._role_response_key(permission_for): role_id,
            "permission_for": permission_for,
            "usertype_id": usertype_id,
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
        Get ALL screens assigned to a staff user type across all mainscreens.
        Grouped by mainscreen for better visibility.
        
        Query params:
        - staffusertype_id: required for staff
        - contractorusertype_id: required for contractor
        - governmentusertype_id: required for government
        - permission_for: staff|contractor (optional; inferred from contractorusertype_id)
        """
        permission_for, role_id = self._role_from_request(request)
        if not role_id:
            return Response(
                {"error": f"{self._role_response_key(permission_for)} is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role_filters = self._role_filter_kwargs(permission_for, role_id)

        # Get ALL permissions for this role type (no mainscreen filter)
        qs = UserScreenPermission.objects.filter(
            is_deleted=False,
            **role_filters,
        ).select_related("mainscreen_id", "usertype_id")

        if not qs.exists():
            return Response(
                {
                    self._role_response_key(permission_for): role_id,
                    "permission_for": permission_for,
                    "mainscreens": [],
                    "total_screens": 0,
                    "usertype_id": None,
                },
                status=status.HTTP_200_OK,
            )

        # Group by mainscreen
        mainscreen_map = {}
        usertype_id = None

        for perm in qs:
            if not usertype_id and perm.usertype_id_id:
                usertype_id = perm.usertype_id_id

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
                self._role_response_key(permission_for): role_id,
                "permission_for": permission_for,
                "usertype_id": usertype_id,
                "mainscreens": mainscreens,
                "total_screens": total_screens,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Delete By Staff + Mainscreen (safe delete)
    # ---------------------------------------------------------
    @action(detail=False, methods=["delete"], url_path=r"delete-by-staffusertype/(?P<staffusertype_id>[^/.]+)/?")
    def delete_by_staffusertype(self, request, staffusertype_id):
        return self._delete_by_usertype(request, staffusertype_id=staffusertype_id)

    @action(detail=False, methods=["delete"], url_path=r"delete-by-contractorusertype/(?P<contractorusertype_id>[^/.]+)/?")
    def delete_by_contractorusertype(self, request, contractorusertype_id):
        return self._delete_by_usertype(request, contractorusertype_id=contractorusertype_id)

    @action(detail=False, methods=["delete"], url_path=r"delete-by-governmentusertype/(?P<governmentusertype_id>[^/.]+)/?")
    def delete_by_governmentusertype(self, request, governmentusertype_id):
        return self._delete_by_usertype(request, governmentusertype_id=governmentusertype_id)

    def _delete_by_usertype(self, request, staffusertype_id=None, contractorusertype_id=None, governmentusertype_id=None):
        mainscreen_id = request.query_params.get("mainscreen_id")
        if not mainscreen_id:
            return Response(
                {"error": "mainscreen_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission_for, role_id = self._role_from_request(
            request,
            default_staffusertype_id=staffusertype_id,
            default_contractorusertype_id=contractorusertype_id,
            default_governmentusertype_id=governmentusertype_id,
        )
        role_filters = self._role_filter_kwargs(permission_for, role_id)

        qs = UserScreenPermission.objects.filter(
            mainscreen_id_id=mainscreen_id,
            is_deleted=False,
            **role_filters,
        )

        deleted_count = qs.count()
        if deleted_count > 0:
            qs.update(is_deleted=True, is_active=False)
            CompanyUserScreenColumnPermission.objects.filter(
                userscreen_id__mainscreen_id_id=mainscreen_id,
                is_deleted=False,
                **role_filters,
            ).update(is_deleted=True, is_active=False)

        return Response(
            {
                "message": "Permissions deleted successfully",
                "deleted_count": deleted_count,
                self._role_response_key(permission_for): role_id,
                "permission_for": permission_for,
                "mainscreen_id": mainscreen_id,
            },
            status=status.HTTP_200_OK,
        )


CompanyUserScreenPermissionViewSet = UserScreenPermissionViewSet
