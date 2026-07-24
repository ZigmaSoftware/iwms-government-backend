from django.db import transaction
from rest_framework import serializers

from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.ward import Ward
from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.superadmin.screen_management.companyuserscreenpermission import UserScreenPermission
from app.models.superadmin.screen_management.dashboardwidgetpermission import DashboardWidgetPermission
from app.models.superadmin.user_management.staff_data_scope import StaffDataScope
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.serializers.superadmin.screen_management.companyuserscreenpermission_serializer import (
    UserScreenPermissionMultiScreenSerializer,
)
from app.serializers.superadmin.user_management.staffcreation_serializer import StaffcreationSerializer


class DashboardPermissionInputSerializer(serializers.Serializer):
    widgetName = serializers.CharField(max_length=50)
    isEnabled = serializers.BooleanField(default=True, required=False)
    orderNo = serializers.IntegerField()


class DataScopeInputSerializer(serializers.Serializer):
    locationNodes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    stateId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    districtId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    areaTypeId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    corporationIds = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True,
    )
    municipalityIds = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True,
    )
    townPanchayatIds = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True,
    )
    panchayatUnionIds = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True,
    )
    panchayatIds = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True,
    )
    wardIds = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True,
    )


class LoginConfigInputSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    confirmPassword = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    userTypeId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    governmentUserTypeId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    accountStatus = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class StaffAccessConfigurationSerializer(serializers.Serializer):
    basicInfo = serializers.DictField()
    loginConfig = LoginConfigInputSerializer()
    permissions = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )
    dashboardPermissions = DashboardPermissionInputSerializer(
        many=True,
        required=False,
    )
    dataScope = DataScopeInputSerializer(required=False)

    def validate(self, data):
        login_config = data.get("loginConfig") or {}
        if login_config.get("password") != login_config.get("confirmPassword"):
            raise serializers.ValidationError({
                "confirmPassword": "Password and confirmPassword do not match."
            })
        return data

    def create(self, validated_data):
        with transaction.atomic():
            return self._save_configuration(validated_data)

    def update(self, instance, validated_data):
        with transaction.atomic():
            return self._save_configuration(validated_data, instance=instance)

    def _save_configuration(self, validated_data, instance=None):
        login_config = validated_data.get("loginConfig") or {}
        staff_payload = dict(validated_data.get("basicInfo") or {})
        self._apply_login_config(staff_payload, login_config)

        if instance is None:
            staff_serializer = StaffcreationSerializer(
                data=staff_payload,
                context=self.context,
            )
        else:
            staff_serializer = StaffcreationSerializer(
                instance,
                data=staff_payload,
                partial=True,
                context=self.context,
            )
        staff_serializer.is_valid(raise_exception=True)
        staff = staff_serializer.save()

        data_scope = self._save_data_scope(
            staff,
            validated_data.get("dataScope") or {},
        )
        access_scope = self._access_scope_payload(data_scope)
        permission_results = self._save_permissions(
            validated_data.get("permissions") or [],
            access_scope,
            staff.staff_unique_id,
        )
        dashboard_permissions = self._save_dashboard_permissions(
            validated_data.get("dashboardPermissions") or [],
            access_scope,
            staff.staff_unique_id,
        )

        return {
            "staff": staff,
            "permissions": permission_results,
            "dashboard_permissions": dashboard_permissions,
            "data_scope": data_scope,
        }

    LOCAL_BODY_M2M_LEVELS = (
        ("corporation", "corporations"),
        ("municipality", "municipalities"),
        ("town_panchayat", "town_panchayats"),
        ("panchayat_union", "panchayat_unions"),
        ("panchayat", "panchayats"),
    )

    def _access_scope_payload(self, scope):
        """
        Derive the permission ownership key (state/district/area_type/
        optional local_body_type/local_body_id) from a saved StaffDataScope
        row. A staff scoped to exactly ONE local body in total keeps today's
        exact behaviour (permissions/dashboard widgets scoped to that body).
        A staff scoped to zero or SEVERAL local bodies falls back to their
        District/State boundary — screens and dashboard widgets are governed
        by the broader geo boundary rather than an ambiguous or merged set
        of local-body-specific configs.
        """
        if not scope:
            return {
                "stateId": None, "districtId": None, "areaTypeId": None,
                "localBodyType": None, "localBodyId": None,
            }

        candidates = [
            (level, local_body_id)
            for level, m2m_field in self.LOCAL_BODY_M2M_LEVELS
            for local_body_id in getattr(scope, m2m_field).values_list("unique_id", flat=True)
        ]
        local_body_type, local_body_id = candidates[0] if len(candidates) == 1 else (None, None)
        return {
            "stateId": scope.state_id,
            "districtId": scope.district_id,
            "areaTypeId": scope.area_type_id,
            "localBodyType": local_body_type,
            "localBodyId": local_body_id,
        }

    def _apply_login_config(self, staff_payload, login_config):
        if "username" in login_config:
            staff_payload["username"] = login_config.get("username")
        if login_config.get("password"):
            staff_payload["password"] = login_config.get("password")
        if login_config.get("governmentUserTypeId"):
            staff_payload["governmentusertype_id"] = login_config.get("governmentUserTypeId")

        account_status = (login_config.get("accountStatus") or "").upper()
        if account_status:
            staff_payload["active_status"] = account_status not in {
                "INACTIVE",
                "DISABLED",
                "SUSPENDED",
            }
            staff_payload["login_enabled"] = account_status in {
                "ACTIVE",
                "APPROVED",
                "ENABLED",
            }

    def _save_permissions(self, permissions, access_scope, staff_id):
        if not access_scope.get("stateId"):
            if permissions:
                raise serializers.ValidationError({
                    "dataScope": "State must be selected before permissions can be assigned."
                })
            return []

        results = []
        for permission in permissions:
            payload = {
                "stateId": access_scope["stateId"],
                "districtId": access_scope["districtId"],
                "areaTypeId": access_scope["areaTypeId"],
                "localBodyType": access_scope["localBodyType"],
                "localBodyId": access_scope["localBodyId"],
                "permissionOwnerKind": "staff",
                "staffId": staff_id,
                "mainScreenId": permission.get("mainScreenId") or permission.get("mainscreen_id"),
                "userScreens": permission.get("userScreens") or permission.get("screens") or [],
                "description": permission.get("description", ""),
            }
            serializer = UserScreenPermissionMultiScreenSerializer(
                data=payload,
                context=self.context,
            )
            serializer.is_valid(raise_exception=True)
            results.append(serializer.save())
        return results

    def _save_dashboard_permissions(self, dashboard_permissions, access_scope, staff_id):
        if not access_scope.get("localBodyType") or not access_scope.get("localBodyId"):
            return []

        saved = []
        for permission in dashboard_permissions:
            obj, _ = DashboardWidgetPermission.objects.update_or_create(
                state_id_id=access_scope["stateId"],
                district_id_id=access_scope["districtId"],
                area_type_id_id=access_scope["areaTypeId"],
                local_body_type=access_scope["localBodyType"],
                local_body_id=access_scope["localBodyId"],
                permission_owner_kind="staff",
                staff_id=staff_id,
                widget_name=permission["widgetName"],
                is_deleted=False,
                defaults={
                    "is_enabled": permission.get("isEnabled", True),
                    "order_no": permission["orderNo"],
                    "is_active": True,
                },
            )
            saved.append(obj)
        return saved

    def _save_data_scope(self, staff, data_scope):
        if not data_scope:
            return None

        location_node_ids = data_scope.get("locationNodes") or []
        state_id = data_scope.get("stateId") or None
        district_id = data_scope.get("districtId") or None
        area_type_id = data_scope.get("areaTypeId") or None
        local_body_ids_by_model = (
            (Corporation, data_scope.get("corporationIds") or [], "corporationIds"),
            (Municipality, data_scope.get("municipalityIds") or [], "municipalityIds"),
            (TownPanchayat, data_scope.get("townPanchayatIds") or [], "townPanchayatIds"),
            (PanchayatUnion, data_scope.get("panchayatUnionIds") or [], "panchayatUnionIds"),
            (Panchayat, data_scope.get("panchayatIds") or [], "panchayatIds"),
        )
        ward_ids = data_scope.get("wardIds") or []

        def _validate(model, value, field_name):
            if value and not model.objects.filter(unique_id=value, is_deleted=False).exists():
                raise serializers.ValidationError({"dataScope": {field_name: f"Invalid {field_name}."}})

        def _validate_many(model, values, field_name):
            valid_ids = set(
                model.objects.filter(unique_id__in=values, is_deleted=False)
                .values_list("unique_id", flat=True)
            )
            invalid_ids = set(values) - valid_ids
            if invalid_ids:
                raise serializers.ValidationError({
                    "dataScope": {field_name: f"Invalid {field_name}: {', '.join(sorted(invalid_ids))}"}
                })

        _validate(State, state_id, "stateId")
        _validate(District, district_id, "districtId")
        _validate(AreaType, area_type_id, "areaTypeId")
        for model, values, field_name in local_body_ids_by_model:
            _validate_many(model, values, field_name)
        _validate_many(Ward, ward_ids, "wardIds")

        valid_node_ids = set(
            HierarchyNode.objects.filter(
                unique_id__in=location_node_ids,
                is_deleted=False,
            ).values_list("unique_id", flat=True)
        )
        invalid_node_ids = set(location_node_ids) - valid_node_ids
        if invalid_node_ids:
            raise serializers.ValidationError({
                "dataScope": {
                    "locationNodes": f"Invalid location nodes: {', '.join(sorted(invalid_node_ids))}"
                }
            })

        scope, _ = StaffDataScope.objects.update_or_create(
            staff=staff,
            is_deleted=False,
            defaults={
                "state_id": state_id,
                "district_id": district_id,
                "area_type_id": area_type_id,
                "is_active": True,
            },
        )
        scope.location_nodes.set(location_node_ids)
        scope.corporations.set(local_body_ids_by_model[0][1])
        scope.municipalities.set(local_body_ids_by_model[1][1])
        scope.town_panchayats.set(local_body_ids_by_model[2][1])
        scope.panchayat_unions.set(local_body_ids_by_model[3][1])
        scope.panchayats.set(local_body_ids_by_model[4][1])
        scope.wards.set(ward_ids)
        return scope

    def _local_body_filters(self, staff):
        scope = (
            StaffDataScope.objects.filter(staff=staff, is_active=True, is_deleted=False)
            .first()
        )
        access_scope = self._access_scope_payload(scope)
        if not access_scope.get("stateId"):
            return {}

        filters = {
            "permission_owner_kind": "staff",
            "staff_id": staff.staff_unique_id,
        }
        if access_scope.get("stateId"):
            filters["state_id_id"] = access_scope["stateId"]
        if access_scope.get("districtId"):
            filters["district_id_id"] = access_scope["districtId"]
        if access_scope.get("areaTypeId"):
            filters["area_type_id_id"] = access_scope["areaTypeId"]
        if access_scope.get("localBodyType") and access_scope.get("localBodyId"):
            filters["local_body_type"] = access_scope["localBodyType"]
            filters["local_body_id"] = access_scope["localBodyId"]
        else:
            filters["local_body_type__isnull"] = True
            filters["local_body_id__isnull"] = True
        return filters

    def _permission_payload(self, staff):
        filters = self._local_body_filters(staff)
        if not filters:
            return []

        permissions = UserScreenPermission.objects.filter(
            is_active=True,
            is_deleted=False,
            **filters,
        ).select_related("mainscreen_id", "userscreen_id", "userscreenaction_id")
        columns = CompanyUserScreenColumnPermission.objects.filter(
            is_active=True,
            is_deleted=False,
            **filters,
        ).select_related("userscreen_id", "userscreen_id__mainscreen_id", "column_id")

        modules = {}
        for permission in permissions.order_by(
            "mainscreen_id__order_no",
            "userscreen_id__order_no",
            "order_no",
        ):
            module = modules.setdefault(
                permission.mainscreen_id_id,
                {
                    "mainScreenId": permission.mainscreen_id_id,
                    "mainScreenName": permission.mainscreen_id.mainscreen_name,
                    "userScreens": {},
                },
            )
            screen = module["userScreens"].setdefault(
                permission.userscreen_id_id,
                {
                    "userScreenId": permission.userscreen_id_id,
                    "userScreenName": permission.userscreen_id.userscreen_name,
                    "actionIds": [],
                    "actions": [],
                    "columns": [],
                },
            )
            action = permission.userscreenaction_id
            if action.unique_id not in screen["actionIds"]:
                screen["actionIds"].append(action.unique_id)
            action_name = action.variable_name or action.action_name
            if action_name and action_name not in screen["actions"]:
                screen["actions"].append(action_name)

        for column_permission in columns.order_by(
            "userscreen_id__mainscreen_id__order_no",
            "userscreen_id__order_no",
            "order_no",
        ):
            userscreen = column_permission.userscreen_id
            mainscreen = userscreen.mainscreen_id
            module = modules.setdefault(
                mainscreen.unique_id,
                {
                    "mainScreenId": mainscreen.unique_id,
                    "mainScreenName": mainscreen.mainscreen_name,
                    "userScreens": {},
                },
            )
            screen = module["userScreens"].setdefault(
                userscreen.unique_id,
                {
                    "userScreenId": userscreen.unique_id,
                    "userScreenName": userscreen.userscreen_name,
                    "actionIds": [],
                    "actions": [],
                    "columns": [],
                },
            )
            column = column_permission.column_id
            screen["columns"].append({
                "columnId": column.unique_id,
                "fieldName": column.field_name,
                "displayName": column.display_name,
                "canView": column_permission.can_view,
                "fieldPermissionState": column_permission.field_permission_state,
                "orderNo": column_permission.order_no,
            })

        payload = []
        for module in modules.values():
            payload.append({
                "mainScreenId": module["mainScreenId"],
                "mainScreenName": module["mainScreenName"],
                "userScreens": list(module["userScreens"].values()),
            })
        return payload

    def _dashboard_payload(self, staff):
        filters = self._local_body_filters(staff)
        if not filters:
            return []
        return [
            {
                "widgetName": permission.widget_name,
                "isEnabled": permission.is_enabled,
                "orderNo": permission.order_no,
            }
            for permission in DashboardWidgetPermission.objects.filter(
                is_active=True,
                is_deleted=False,
                **filters,
            ).order_by("order_no")
        ]

    def _data_scope_payload(self, staff):
        scope = (
            StaffDataScope.objects.filter(staff=staff, is_active=True, is_deleted=False)
            .prefetch_related(
                "location_nodes",
                "corporations",
                "municipalities",
                "town_panchayats",
                "panchayat_unions",
                "panchayats",
                "wards",
            )
            .first()
        )
        if not scope:
            # No dedicated StaffAccessConfiguration scope saved yet — fall back
            # to the geo scope captured directly on the staff record at
            # creation time (StaffcreationOfficeDetails.state/district/...),
            # so the two forms agree until an explicit access-config save
            # creates its own StaffDataScope row.
            local_body_pairs = (
                ("corporation_id", staff.corporation_id),
                ("municipality_id", staff.municipality_id),
                ("town_panchayat_id", staff.town_panchayat_id),
                ("panchayat_union_id", staff.panchayat_union_id),
                ("panchayat_id", staff.panchayat_id),
            )
            local_body_level, local_body_id = next(
                ((level, value) for level, value in local_body_pairs if value),
                (None, None),
            )
            return {
                "locationNodes": [],
                "stateId": staff.state_id,
                "districtId": staff.district_id,
                "areaTypeId": staff.area_type_id,
                "corporationIds": [staff.corporation_id] if staff.corporation_id else [],
                "municipalityIds": [staff.municipality_id] if staff.municipality_id else [],
                "townPanchayatIds": [staff.town_panchayat_id] if staff.town_panchayat_id else [],
                "panchayatUnionIds": [staff.panchayat_union_id] if staff.panchayat_union_id else [],
                "panchayatIds": [staff.panchayat_id] if staff.panchayat_id else [],
                "wardIds": [],
                "localBodyLevel": local_body_level,
                "localBodyId": local_body_id,
            }

        corporation_ids = list(scope.corporations.values_list("unique_id", flat=True))
        municipality_ids = list(scope.municipalities.values_list("unique_id", flat=True))
        town_panchayat_ids = list(scope.town_panchayats.values_list("unique_id", flat=True))
        panchayat_union_ids = list(scope.panchayat_unions.values_list("unique_id", flat=True))
        panchayat_ids = list(scope.panchayats.values_list("unique_id", flat=True))
        ward_ids = list(scope.wards.values_list("unique_id", flat=True))

        candidates = [
            (level, local_body_id)
            for level, ids in (
                ("corporation_id", corporation_ids),
                ("municipality_id", municipality_ids),
                ("town_panchayat_id", town_panchayat_ids),
                ("panchayat_union_id", panchayat_union_ids),
                ("panchayat_id", panchayat_ids),
            )
            for local_body_id in ids
        ]
        # Backward-compatible single value for consumers still expecting one
        # local body — populated only when exactly one is selected in total.
        local_body_level, local_body_id = candidates[0] if len(candidates) == 1 else (None, None)

        return {
            "locationNodes": list(scope.location_nodes.values_list("unique_id", flat=True)),
            "stateId": scope.state_id,
            "districtId": scope.district_id,
            "areaTypeId": scope.area_type_id,
            "corporationIds": corporation_ids,
            "municipalityIds": municipality_ids,
            "townPanchayatIds": town_panchayat_ids,
            "panchayatUnionIds": panchayat_union_ids,
            "panchayatIds": panchayat_ids,
            "wardIds": ward_ids,
            "localBodyLevel": local_body_level,
            "localBodyId": local_body_id,
        }

    def _configuration_payload(self, staff):
        staff_payload = StaffcreationSerializer(staff, context=self.context).data
        usertype_id = getattr(staff, "user_type_id_id", None) or staff_payload.get("user_type_id")
        permissions = self._permission_payload(staff)
        dashboard_permissions = self._dashboard_payload(staff)
        data_scope = self._data_scope_payload(staff)
        account_status = "ACTIVE" if getattr(staff, "login_enabled", False) else "INACTIVE"

        return {
            **staff_payload,
            "role_label": (
                staff_payload.get("staffusertype_name")
                or staff_payload.get("contractorusertype_name")
                or staff_payload.get("governmentusertype_name")
            ),
            "permission_count": sum(
                1
                for module in permissions
                for screen in (module.get("userScreens") or [])
                if screen.get("actionIds")
            ),
            "account_status": account_status,
            "basicInfo": {
                "employeeName": staff_payload.get("employee_name") or "",
                "staffConfigName": staff_payload.get("staff_config_name") or "",
                "mobileNumber": staff_payload.get("contact_mobile") or "",
                "officeEmail": staff_payload.get("contact_email") or "",
                "departmentId": staff_payload.get("department_id") or "",
                # Designation is free text now (not an FK master).
                "designation": staff_payload.get("designation") or "",
                "doj": staff_payload.get("doj") or "",
                "activeStatus": staff_payload.get("active_status", True),
            },
            "loginConfig": {
                "username": staff_payload.get("username") or "",
                "password": staff_payload.get("password") or "",
                "confirmPassword": staff_payload.get("password") or "",
                "userTypeId": usertype_id or "",
                "governmentUserTypeId": staff_payload.get("governmentusertype_id") or "",
                "loginEnabled": getattr(staff, "login_enabled", False),
                "accountStatus": account_status,
            },
            "permissions": permissions,
            "dashboardPermissions": dashboard_permissions,
            "dataScope": data_scope,
        }

    def to_representation(self, instance):
        staff = instance.get("staff") if isinstance(instance, dict) else instance
        return self._configuration_payload(staff)

    class Meta:
        model = Staffcreation
