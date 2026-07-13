from collections import defaultdict

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.serializers.screen_managements.companyuserscreenpermission_serializer import (
    UserScreenPermissionMultiScreenSerializer,
)
from app.serializers.screen_managements.userscreencolumn_serializer import (
    UserScreenColumnSerializer,
)
from app.services.schema_sync_service import sync_userscreen_schema


class UserScreenColumnsAPIView(APIView):
    def get(self, request, userscreen_id):
        userscreen = UserScreen.objects.filter(
            unique_id=userscreen_id,
            is_deleted=False,
        ).first()
        if not userscreen:
            return Response({"error": "Invalid userscreen"}, status=status.HTTP_404_NOT_FOUND)

        sync_userscreen_schema(userscreen)
        columns = UserScreenColumn.objects.filter(
            userscreen_id=userscreen,
            is_deleted=False,
            is_active=True,
        ).order_by("order_no")
        return Response(UserScreenColumnSerializer(columns, many=True).data)


class PermissionAssignAPIView(APIView):
    @transaction.atomic
    def post(self, request):
        payload = request.data
        normalized_payloads = self._normalize_payload(payload)
        results = []

        for item in normalized_payloads:
            serializer = UserScreenPermissionMultiScreenSerializer(data=item)
            serializer.is_valid(raise_exception=True)
            results.append(serializer.save())

        return Response(
            {
                "message": "Permissions assigned successfully",
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

    def _normalize_payload(self, payload):
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
                "staffUserTypeId": payload.get("staffUserTypeId") or payload.get("staffusertype_id"),
                "contractorUserTypeId": (
                    payload.get("contractorUserTypeId")
                    or payload.get("contractorusertype_id")
                ),
                "mainScreenId": permission.get("mainScreenId") or permission.get("mainscreen_id"),
                "userScreens": permission.get("userScreens") or permission.get("screens") or [],
                "description": payload.get("description", ""),
            })
        return normalized


class UserPermissionsAPIView(APIView):
    def get(self, request, *_args, **_kwargs):
        staffusertype_id = (
            request.query_params.get("staffUserTypeId")
            or request.query_params.get("staffusertype_id")
        )
        contractorusertype_id = (
            request.query_params.get("contractorUserTypeId")
            or request.query_params.get("contractorusertype_id")
        )
        usertype_id = request.query_params.get("usertypeId") or request.query_params.get("usertype_id")

        action_qs = UserScreenPermission.objects.filter(
            is_active=True,
            is_deleted=False,
        ).select_related("mainscreen_id", "userscreen_id", "userscreenaction_id")
        column_qs = CompanyUserScreenColumnPermission.objects.filter(
            is_active=True,
            is_deleted=False,
        ).select_related("userscreen_id", "column_id")

        if staffusertype_id:
            action_qs = action_qs.filter(staffusertype_id_id=staffusertype_id)
            column_qs = column_qs.filter(staffusertype_id_id=staffusertype_id)
        if contractorusertype_id:
            action_qs = action_qs.filter(contractorusertype_id_id=contractorusertype_id)
            column_qs = column_qs.filter(contractorusertype_id_id=contractorusertype_id)
        if usertype_id:
            action_qs = action_qs.filter(usertype_id_id=usertype_id)
            column_qs = column_qs.filter(usertype_id_id=usertype_id)

        action_map = defaultdict(lambda: {
            "view": False,
            "add": False,
            "edit": False,
            "delete": False,
        })
        for permission in action_qs:
            action = (permission.userscreenaction_id.variable_name or permission.userscreenaction_id.action_name).lower()
            if action in action_map[permission.userscreen_id_id]:
                action_map[permission.userscreen_id_id][action] = True

        column_map = defaultdict(list)
        for permission in column_qs:
            column = permission.column_id
            column_map[permission.userscreen_id_id].append({
                "id": column.unique_id,
                "fieldName": column.field_name,
                "displayName": column.display_name,
                "dataType": column.data_type,
                "dbColumn": column.db_column,
                "canView": permission.can_view,
                "isRequired": column.is_required,
                "orderNo": permission.order_no,
            })

        userscreen_ids = set(action_map.keys()) | set(column_map.keys())
        screens = UserScreen.objects.filter(
            unique_id__in=userscreen_ids,
            is_deleted=False,
        ).order_by("order_no")

        response = [
            {
                "userScreenId": screen.unique_id,
                "userScreenName": screen.userscreen_name,
                "permissions": action_map[screen.unique_id],
                "columns": column_map.get(screen.unique_id, []),
            }
            for screen in screens
        ]

        return Response({
            "contractorUserTypeId": contractorusertype_id,
            "permissions": response,
        })
