from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.screen_managements.userscreencolumn import UserScreenColumn

from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.screen_managements.companyuserscreenpermission import (
    LocalBodyType,
    PermissionOwnerKind,
    PermissionType,
)

LOCAL_BODY_MODELS = {
    LocalBodyType.CORPORATION: "app.models.masters.corporation.Corporation",
    LocalBodyType.MUNICIPALITY: "app.models.masters.municipality.Municipality",
    LocalBodyType.PANCHAYAT: "app.models.masters.panchayat.Panchayat",
    LocalBodyType.TOWN_PANCHAYAT: "app.models.masters.town_panchayat.TownPanchayat",
    LocalBodyType.PANCHAYAT_UNION: "app.models.masters.panchayat_union.PanchayatUnion",
}


def _resolve_local_body_model(local_body_type):
    import importlib

    dotted = LOCAL_BODY_MODELS.get(local_body_type)
    if not dotted:
        return None
    module_path, class_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


SUPPORTED_ACTION_NAMES = {"add", "edit", "delete", "view"}


class UserScreenPermissionSerializer(serializers.ModelSerializer):
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    userscreenaction_name = serializers.CharField(source="userscreenaction_id.action_name", read_only=True)
    usertype_name = serializers.CharField(source="usertype_id.name", read_only=True)
    staffusertype_name = serializers.SerializerMethodField()
    contractorusertype_name = serializers.CharField(
        source="contractorusertype_id.name",
        read_only=True,
    )
    governmentusertype_name = serializers.SerializerMethodField()
    mainscreen_name = serializers.CharField(source="mainscreen_id.mainscreen_name", read_only=True)

    class Meta:
        model = UserScreenPermission
        fields = "__all__"

    def get_staffusertype_name(self, obj):
        staffusertype = getattr(obj, "staffusertype_id", None)
        if staffusertype:
            return staffusertype.name
        contractorusertype = getattr(obj, "contractorusertype_id", None)
        if contractorusertype:
            return contractorusertype.name
        governmentusertype = getattr(obj, "governmentusertype_id", None)
        if governmentusertype:
            if hasattr(governmentusertype, "get_name_display"):
                return governmentusertype.get_name_display()
            return governmentusertype.name
        return None

    def get_governmentusertype_name(self, obj):
        governmentusertype = getattr(obj, "governmentusertype_id", None)
        if not governmentusertype:
            return None
        if hasattr(governmentusertype, "get_name_display"):
            return governmentusertype.get_name_display()
        return governmentusertype.name

    def to_representation(self, instance):
        data = super().to_representation(instance)
        contractorusertype_id = data.get("contractorusertype_id")
        governmentusertype_id = data.get("governmentusertype_id")

        if contractorusertype_id and not data.get("staffusertype_id"):
            data["staffusertype_id"] = contractorusertype_id
            data["staffUserTypeId"] = contractorusertype_id
        if governmentusertype_id and not data.get("staffusertype_id"):
            data["staffusertype_id"] = governmentusertype_id
            data["staffUserTypeId"] = governmentusertype_id

        data["contractorUserTypeId"] = contractorusertype_id
        data["governmentUserTypeId"] = governmentusertype_id
        # Local-Body ownership (current model) takes precedence; the legacy
        # role-based fields above are only ever populated on old rows kept
        # for backward-compatible reads.
        if data.get("local_body_type") and data.get("local_body_id"):
            data["permission_for"] = data.get("permission_owner_kind") or "super_admin"
        else:
            data["permission_for"] = (
                "government"
                if governmentusertype_id
                else "contractor"
                if contractorusertype_id
                else "staff"
            )
        return data


class ScreenActionSerializer(serializers.Serializer):
    userscreen_id = serializers.CharField(required=False)
    userScreenId = serializers.CharField(required=False)
    actions = serializers.ListField(child=serializers.JSONField(), allow_empty=True, required=False)
    actionIds = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    columnIds = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    columns = serializers.ListField(child=serializers.DictField(), allow_empty=True, required=False)
    meta = serializers.DictField(required=False)

    def validate(self, data):
        data["userscreen_id"] = data.get("userscreen_id") or data.get("userScreenId")
        screen_is_active = (data.get("meta") or {}).get("isActive", True)

        action_ids = data.get("actionIds")
        if action_ids is None:
            action_ids = []
            for action in data.get("actions", []):
                if isinstance(action, dict):
                    if action.get("isActive", action.get("is_active", True)):
                        action_id = action.get("actionId") or action.get("action_id") or action.get("id")
                        if action_id:
                            action_ids.append(action_id)
                elif action:
                    action_ids.append(action)
        data["actionIds"] = action_ids

        column_permissions = None
        if "columns" in data:
            column_permissions = []
            for column in data.get("columns", []):
                column_id = column.get("columnId") or column.get("column_id") or column.get("id")
                if not column_id:
                    raise serializers.ValidationError({"columns": "columnId is required."})
                column_permissions.append({
                    "column_id": column_id,
                    "field_name": column.get("fieldName") or column.get("field_name"),
                    "can_view": column.get("canView", column.get("can_view", True)),
                    "field_permission_state": column.get("fieldPermissionState") or column.get("field_permission_state"),
                    "order_no": column.get("orderNo") or column.get("order_no"),
                    "is_required": column.get("isRequired", column.get("is_required")),
                })
            data["columnIds"] = [item["column_id"] for item in column_permissions]
        else:
            data["columnIds"] = data.get("columnIds", None)

        data["columnPermissions"] = column_permissions
        if not screen_is_active:
            data["actionIds"] = []
            if column_permissions is not None:
                data["columnPermissions"] = []
                data["columnIds"] = []
        if not data["userscreen_id"]:
            raise serializers.ValidationError({"userscreen_id": "This field is required."})
        return data


class UserScreenPermissionMultiScreenSerializer(serializers.Serializer):
    usertype_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    usertypeId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    userTypeId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    staffUserTypeId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    mainscreen_id = serializers.CharField(required=False)
    mainScreenId = serializers.CharField(required=False)
    screens = ScreenActionSerializer(many=True, required=False)
    userScreens = ScreenActionSerializer(many=True, required=False)
    description = serializers.CharField(required=False, allow_blank=True)

    contractorusertype_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    contractorUserTypeId = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    governmentusertype_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    governmentUserTypeId = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    state_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    stateId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    district_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    districtId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    area_type_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    areaTypeId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    local_body_type = serializers.ChoiceField(
        choices=LocalBodyType.choices, required=False, allow_null=True, allow_blank=True,
    )
    localBodyType = serializers.ChoiceField(
        choices=LocalBodyType.choices, required=False, allow_null=True, allow_blank=True,
    )
    local_body_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    localBodyId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    permission_type = serializers.ChoiceField(
        choices=PermissionType.choices, required=False, allow_null=True, allow_blank=True,
    )
    permissionType = serializers.ChoiceField(
        choices=PermissionType.choices, required=False, allow_null=True, allow_blank=True,
    )
    permission_owner_kind = serializers.ChoiceField(
        choices=PermissionOwnerKind.choices, required=False, allow_null=True, allow_blank=True,
    )
    permissionOwnerKind = serializers.ChoiceField(
        choices=PermissionOwnerKind.choices, required=False, allow_null=True, allow_blank=True,
    )
    staff_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    staffId = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate(self, data):
        data["state_id"] = (data.get("state_id") or data.get("stateId") or "").strip() or None
        data["district_id"] = (data.get("district_id") or data.get("districtId") or "").strip() or None
        data["area_type_id"] = (data.get("area_type_id") or data.get("areaTypeId") or "").strip() or None
        data["local_body_type"] = (data.get("local_body_type") or data.get("localBodyType") or "").strip() or None
        data["local_body_id"] = (data.get("local_body_id") or data.get("localBodyId") or "").strip() or None
        data["permission_type"] = (
            data.get("permission_type") or data.get("permissionType") or PermissionType.SCREEN
        )
        data["permission_owner_kind"] = (
            data.get("permission_owner_kind") or data.get("permissionOwnerKind") or PermissionOwnerKind.SUPER_ADMIN
        )
        data["staff_id"] = (data.get("staff_id") or data.get("staffId") or "").strip() or None

        if data["permission_owner_kind"] == PermissionOwnerKind.STAFF and not data["staff_id"]:
            raise serializers.ValidationError({
                "staff_id": "staff_id is required when permission_owner_kind is 'staff'."
            })

        data["mainscreen_id"] = (data.get("mainscreen_id") or data.get("mainScreenId") or "").strip()
        data["screens"] = data.get("screens") or data.get("userScreens") or []

        if not data["mainscreen_id"]:
            raise serializers.ValidationError({"mainscreen_id": "This field is required."})
        if not data["screens"]:
            raise serializers.ValidationError({"screens": "At least one screen required."})

        has_partial_local_body = bool(data["local_body_type"]) != bool(data["local_body_id"])
        if has_partial_local_body:
            raise serializers.ValidationError({
                "local_body_id": "local_body_type and local_body_id must be supplied together."
            })

        state = None
        district = None
        area_type = None

        if data["state_id"]:
            try:
                state = State.objects.get(unique_id=data["state_id"], is_deleted=False)
            except State.DoesNotExist:
                raise serializers.ValidationError({"state_id": "Invalid state"})
        if data["district_id"]:
            try:
                district = District.objects.get(unique_id=data["district_id"], is_deleted=False)
            except District.DoesNotExist:
                raise serializers.ValidationError({"district_id": "Invalid district"})
        if data["area_type_id"]:
            try:
                area_type = AreaType.objects.get(unique_id=data["area_type_id"], is_deleted=False)
            except AreaType.DoesNotExist:
                raise serializers.ValidationError({"area_type_id": "Invalid area_type"})

        local_body_type = data["local_body_type"]
        local_body_id = data["local_body_id"]
        if local_body_type and local_body_id:
            local_body_model = _resolve_local_body_model(local_body_type)
            if not local_body_model:
                raise serializers.ValidationError({"local_body_type": "Invalid local_body_type"})
            try:
                local_body_model.objects.get(unique_id=local_body_id, is_deleted=False)
            except local_body_model.DoesNotExist:
                raise serializers.ValidationError({"local_body_id": "Invalid local_body_id for local_body_type"})

        try:
            mainscreen = MainScreen.objects.get(unique_id=data["mainscreen_id"], is_deleted=False)
        except MainScreen.DoesNotExist:
            raise serializers.ValidationError({"mainscreen_id": "Invalid mainscreen"})

        screen_ids = {screen["userscreen_id"] for screen in data["screens"]}
        valid_screen_ids = set(
            UserScreen.objects.filter(
                unique_id__in=screen_ids,
                mainscreen_id_id=mainscreen.unique_id,
                is_deleted=False,
            ).values_list("unique_id", flat=True)
        )
        invalid_screens = screen_ids - valid_screen_ids
        if invalid_screens:
            raise serializers.ValidationError({
                "screens": f"Invalid userscreens for mainscreen: {', '.join(sorted(invalid_screens))}"
            })

        action_values = {
            str(action_id).strip()
            for screen in data["screens"]
            for action_id in screen.get("actionIds", [])
            if str(action_id).strip()
        }
        if action_values:
            for action_value in action_values:
                normalized = action_value.lower()
                if normalized in SUPPORTED_ACTION_NAMES:
                    UserScreenAction.objects.get_or_create(
                        action_name=normalized,
                        defaults={
                            "variable_name": normalized,
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )

            actions = UserScreenAction.objects.filter(is_deleted=False)
            action_lookup = {}
            for action in actions:
                action_lookup[str(action.unique_id).lower()] = action.unique_id
                action_lookup[(action.action_name or "").lower()] = action.unique_id
                action_lookup[(action.variable_name or "").lower()] = action.unique_id

            invalid_actions = []
            for screen in data["screens"]:
                normalized_action_ids = []
                for action_value in screen.get("actionIds", []):
                    resolved_action_id = action_lookup.get(str(action_value).strip().lower())
                    if resolved_action_id:
                        normalized_action_ids.append(resolved_action_id)
                    else:
                        invalid_actions.append(str(action_value))
                screen["actionIds"] = normalized_action_ids

            if invalid_actions:
                raise serializers.ValidationError({
                    "screens": f"Invalid actions: {', '.join(sorted(invalid_actions))}"
                })

        for screen in data["screens"]:
            column_ids = screen.get("columnIds")
            if column_ids is None:
                continue
            screen_columns = UserScreenColumn.objects.filter(
                userscreen_id_id=screen["userscreen_id"],
                is_active=True,
                is_deleted=False,
            )
            column_lookup = {}
            for column in screen_columns:
                column_lookup[str(column.unique_id).lower()] = column
                column_lookup[(column.field_name or "").lower()] = column

            normalized_column_ids = []
            invalid_columns = []

            if screen.get("columnPermissions") is not None:
                for column_permission in screen["columnPermissions"]:
                    lookup_values = [
                        column_permission.get("column_id"),
                        column_permission.get("field_name"),
                    ]
                    column = None
                    for lookup_value in lookup_values:
                        if lookup_value:
                            column = column_lookup.get(str(lookup_value).strip().lower())
                            if column:
                                break
                    if not column:
                        invalid_columns.append(str(column_permission.get("column_id")))
                        continue
                    field_name = column_permission.get("field_name")
                    if field_name and field_name != column.field_name:
                        raise serializers.ValidationError({
                            "columns": (
                                f"fieldName '{field_name}' does not match "
                                f"columnId '{column.unique_id}'."
                            )
                        })
                    column_permission["column_id"] = column.unique_id
                    column_permission["field_name"] = column.field_name
                    normalized_column_ids.append(column.unique_id)
            else:
                for column_id in column_ids:
                    column = column_lookup.get(str(column_id).strip().lower())
                    if column:
                        normalized_column_ids.append(column.unique_id)
                    else:
                        invalid_columns.append(str(column_id))

            if invalid_columns:
                raise serializers.ValidationError({
                    "columnIds": (
                        "Columns do not belong to the selected userscreen: "
                        f"{', '.join(sorted(invalid_columns))}"
                    )
                })
            screen["columnIds"] = normalized_column_ids

        data["resolved_state_id"] = state.unique_id if state else None
        data["resolved_district_id"] = district.unique_id if district else None
        data["resolved_area_type_id"] = area_type.unique_id if area_type else None
        data["resolved_local_body_type"] = local_body_type
        data["resolved_local_body_id"] = local_body_id
        data["resolved_mainscreen_id"] = mainscreen.unique_id
        return data

    @transaction.atomic
    def create(self, validated_data):
        state_id = validated_data.get("resolved_state_id")
        district_id = validated_data.get("resolved_district_id")
        area_type_id = validated_data.get("resolved_area_type_id")
        local_body_type = validated_data["resolved_local_body_type"]
        local_body_id = validated_data["resolved_local_body_id"]
        permission_type = validated_data.get("permission_type") or PermissionType.SCREEN
        permission_owner_kind = validated_data.get("permission_owner_kind") or PermissionOwnerKind.SUPER_ADMIN
        staff_id = validated_data.get("staff_id")
        mainscreen_id = validated_data["resolved_mainscreen_id"]
        screens = validated_data["screens"]
        desc = (validated_data.get("description") or "").strip()
        update_only = bool(self.context.get("update_only", False))

        created, updated, deleted = [], [], []
        created_columns, updated_columns, deleted_columns = [], [], []

        existing_qs = UserScreenPermission.objects.select_related(
            "userscreen_id", "userscreenaction_id"
        ).filter(
            state_id_id=state_id,
            district_id_id=district_id,
            area_type_id_id=area_type_id,
            local_body_type=local_body_type,
            local_body_id=local_body_id,
            permission_owner_kind=permission_owner_kind,
            staff_id=staff_id,
            permission_type=permission_type,
            mainscreen_id_id=mainscreen_id,
        )
        existing_lookup = {
            (obj.userscreen_id_id, obj.userscreenaction_id_id): obj
            for obj in existing_qs
        }
        incoming_action_keys = set()

        for screen in screens:
            screen_id = screen["userscreen_id"]
            screen_meta = screen.get("meta") or {}
            screen_desc = screen_meta.get("description", desc)
            for order_no, action_id in enumerate(screen.get("actionIds", []), start=1):
                key = (screen_id, action_id)
                incoming_action_keys.add(key)
                permission = existing_lookup.get(key)
                if permission:
                    permission.is_deleted = False
                    permission.is_active = True
                    permission.order_no = order_no
                    permission.description = screen_desc
                    permission.save(update_fields=[
                        "is_deleted",
                        "is_active",
                        "order_no",
                        "description",
                        "updated_at",
                    ])
                    updated.append(permission)
                    continue

                if update_only:
                    raise serializers.ValidationError({
                        "screens": f"Update mode cannot create {screen_id}:{action_id}"
                    })

                permission = UserScreenPermission.objects.create(
                    state_id_id=state_id,
                    district_id_id=district_id,
                    area_type_id_id=area_type_id,
                    local_body_type=local_body_type,
                    local_body_id=local_body_id,
                    permission_type=permission_type,
                    permission_owner_kind=permission_owner_kind,
                    staff_id=staff_id,
                    mainscreen_id_id=mainscreen_id,
                    userscreen_id_id=screen_id,
                    userscreenaction_id_id=action_id,
                    order_no=order_no,
                    description=screen_desc,
                    is_deleted=False,
                    is_active=True,
                )
                created.append(permission)

            if "columnIds" in screen and screen["columnIds"] is not None:
                result = self._sync_column_permissions(
                    state_id=state_id,
                    district_id=district_id,
                    area_type_id=area_type_id,
                    local_body_type=local_body_type,
                    local_body_id=local_body_id,
                    permission_owner_kind=permission_owner_kind,
                    staff_id=staff_id,
                    userscreen_id=screen_id,
                    column_permissions=screen.get("columnPermissions"),
                    column_ids=screen["columnIds"],
                    description=screen_desc,
                )
                created_columns.extend(result["created"])
                updated_columns.extend(result["updated"])
                deleted_columns.extend(result["deleted"])

        for key, permission in existing_lookup.items():
            if key not in incoming_action_keys and not permission.is_deleted:
                permission.is_deleted = True
                permission.is_active = False
                permission.save(update_fields=["is_deleted", "is_active", "updated_at"])
                deleted.append(permission)

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted,
            "created_columns": created_columns,
            "updated_columns": updated_columns,
            "deleted_columns": deleted_columns,
        }

    def _sync_column_permissions(
        self,
        *,
        state_id,
        district_id,
        area_type_id,
        local_body_type,
        local_body_id,
        permission_owner_kind,
        staff_id,
        userscreen_id,
        column_ids,
        column_permissions,
        description,
    ):
        existing = {
            obj.column_id_id: obj
            for obj in CompanyUserScreenColumnPermission.objects.filter(
                state_id_id=state_id,
                district_id_id=district_id,
                area_type_id_id=area_type_id,
                local_body_type=local_body_type,
                local_body_id=local_body_id,
                permission_owner_kind=permission_owner_kind,
                staff_id=staff_id,
                userscreen_id_id=userscreen_id,
            )
        }

        if column_permissions is None:
            column_permissions = [
                {"column_id": column_id, "can_view": True, "order_no": index}
                for index, column_id in enumerate(column_ids, start=1)
            ]

        incoming = {item["column_id"] for item in column_permissions}
        created = []
        updated = []
        deleted = []

        for fallback_order_no, column_permission in enumerate(column_permissions, start=1):
            column_id = column_permission["column_id"]
            order_no = column_permission.get("order_no") or fallback_order_no
            can_view = bool(column_permission.get("can_view", True))
            field_permission_state = column_permission.get("field_permission_state")
            if not field_permission_state:
                field_permission_state = (
                    CompanyUserScreenColumnPermission.VISIBLE
                    if can_view
                    else CompanyUserScreenColumnPermission.HIDDEN
                )
            permission = existing.get(column_id)
            if permission:
                permission.field_permission_state = field_permission_state
                permission.order_no = order_no
                permission.description = description
                permission.is_deleted = False
                permission.is_active = True
                permission.updated_at = timezone.now()
                updated.append(permission)
                continue

            created.append(
                CompanyUserScreenColumnPermission(
                    state_id_id=state_id,
                    district_id_id=district_id,
                    area_type_id_id=area_type_id,
                    local_body_type=local_body_type,
                    local_body_id=local_body_id,
                    permission_owner_kind=permission_owner_kind,
                    staff_id=staff_id,
                    userscreen_id_id=userscreen_id,
                    column_id_id=column_id,
                    field_permission_state=field_permission_state,
                    order_no=order_no,
                    description=description,
                    is_deleted=False,
                    is_active=True,
                )
            )

        for column_id, permission in existing.items():
            if column_id not in incoming and not permission.is_deleted:
                permission.is_deleted = True
                permission.is_active = False
                permission.updated_at = timezone.now()
                deleted.append(permission)

        if created:
            CompanyUserScreenColumnPermission.objects.bulk_create(created)
        if updated:
            CompanyUserScreenColumnPermission.objects.bulk_update(
                updated,
                ["field_permission_state", "order_no", "description", "is_deleted", "is_active", "updated_at"],
            )
        if deleted:
            CompanyUserScreenColumnPermission.objects.bulk_update(
                deleted,
                ["is_deleted", "is_active", "updated_at"],
            )

        return {"created": created, "updated": updated, "deleted": deleted}


CompanyUserScreenPermissionSerializer = UserScreenPermissionSerializer
CompanyUserScreenPermissionMultiScreenSerializer = UserScreenPermissionMultiScreenSerializer
