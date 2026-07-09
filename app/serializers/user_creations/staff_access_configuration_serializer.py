from django.db import transaction
from rest_framework import serializers

from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.models.screen_managements.dashboardwidgetpermission import DashboardWidgetPermission
from app.models.user_creations.staff_data_scope import StaffDataScope
from app.models.user_creations.staffcreation import Staffcreation
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.serializers.screen_managements.companyuserscreenpermission_serializer import (
    UserScreenPermissionMultiScreenSerializer,
)
from app.serializers.user_creations.staffcreation_serializer import StaffcreationSerializer


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
    corporationId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    municipalityId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    townPanchayatId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    panchayatUnionId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    panchayatId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    depotId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    vehicleId = serializers.CharField(required=False, allow_blank=True, allow_null=True)


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

        role_payload = self._role_payload(staff, login_config)
        permission_results = self._save_permissions(
            validated_data.get("permissions") or [],
            role_payload,
        )
        dashboard_permissions = self._save_dashboard_permissions(
            validated_data.get("dashboardPermissions") or [],
            role_payload,
        )
        data_scope = self._save_data_scope(
            staff,
            validated_data.get("dataScope") or {},
        )

        return {
            "staff": staff,
            "permissions": permission_results,
            "dashboard_permissions": dashboard_permissions,
            "data_scope": data_scope,
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

    def _role_payload(self, staff, login_config):
        return {
            "userTypeId": (
                login_config.get("userTypeId")
                or getattr(staff, "user_type_id_id", None)
            ),
            "governmentUserTypeId": (
                login_config.get("governmentUserTypeId")
                or getattr(staff, "governmentusertype_id_id", None)
            ),
        }

    def _save_permissions(self, permissions, role_payload):
        results = []
        for permission in permissions:
            payload = {
                "userTypeId": (
                    permission.get("userTypeId")
                    or permission.get("usertypeId")
                    or permission.get("usertype_id")
                    or role_payload["userTypeId"]
                ),
                "governmentUserTypeId": (
                    permission.get("governmentUserTypeId")
                    or permission.get("governmentusertype_id")
                    or role_payload["governmentUserTypeId"]
                ),
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

    def _save_dashboard_permissions(self, dashboard_permissions, role_payload):
        saved = []
        for permission in dashboard_permissions:
            obj, _ = DashboardWidgetPermission.objects.update_or_create(
                usertype_id_id=role_payload["userTypeId"],
                staffusertype_id_id=None,
                contractorusertype_id_id=None,
                governmentusertype_id_id=role_payload["governmentUserTypeId"],
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

        depot_id = data_scope.get("depotId") or None
        vehicle_id = data_scope.get("vehicleId") or None
        location_node_ids = data_scope.get("locationNodes") or []
        state_id = data_scope.get("stateId") or None
        district_id = data_scope.get("districtId") or None
        area_type_id = data_scope.get("areaTypeId") or None
        corporation_id = data_scope.get("corporationId") or None
        municipality_id = data_scope.get("municipalityId") or None
        town_panchayat_id = data_scope.get("townPanchayatId") or None
        panchayat_union_id = data_scope.get("panchayatUnionId") or None
        panchayat_id = data_scope.get("panchayatId") or None

        if depot_id and not HierarchyNode.objects.filter(unique_id=depot_id, is_deleted=False).exists():
            raise serializers.ValidationError({"dataScope": {"depotId": "Invalid depotId."}})
        if vehicle_id and not VehicleCreation.objects.filter(unique_id=vehicle_id, is_deleted=False).exists():
            raise serializers.ValidationError({"dataScope": {"vehicleId": "Invalid vehicleId."}})

        def _validate(model, value, field_name):
            if value and not model.objects.filter(unique_id=value, is_deleted=False).exists():
                raise serializers.ValidationError({"dataScope": {field_name: f"Invalid {field_name}."}})

        _validate(State, state_id, "stateId")
        _validate(District, district_id, "districtId")
        _validate(AreaType, area_type_id, "areaTypeId")
        _validate(Corporation, corporation_id, "corporationId")
        _validate(Municipality, municipality_id, "municipalityId")
        _validate(TownPanchayat, town_panchayat_id, "townPanchayatId")
        _validate(PanchayatUnion, panchayat_union_id, "panchayatUnionId")
        _validate(Panchayat, panchayat_id, "panchayatId")

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
                "depot_id": depot_id,
                "vehicle_id": vehicle_id,
                "state_id": state_id,
                "district_id": district_id,
                "area_type_id": area_type_id,
                "corporation_id": corporation_id,
                "municipality_id": municipality_id,
                "town_panchayat_id": town_panchayat_id,
                "panchayat_union_id": panchayat_union_id,
                "panchayat_id": panchayat_id,
                "is_active": True,
            },
        )
        scope.location_nodes.set(location_node_ids)
        return scope

    def _role_filters(self, staff):
        usertype_id = getattr(staff, "user_type_id_id", None)
        staffusertype_id = getattr(staff, "staffusertype_id_id", None)
        contractorusertype_id = getattr(staff, "contractorusertype_id_id", None)
        governmentusertype_id = getattr(staff, "governmentusertype_id_id", None)

        if not usertype_id:
            role = (
                getattr(staff, "staffusertype_id", None)
                or getattr(staff, "contractorusertype_id", None)
                or getattr(staff, "governmentusertype_id", None)
            )
            usertype_id = getattr(getattr(role, "usertype_id", None), "unique_id", None)

        filters = {"usertype_id_id": usertype_id}
        if staffusertype_id:
            filters["staffusertype_id_id"] = staffusertype_id
        elif contractorusertype_id:
            filters["contractorusertype_id_id"] = contractorusertype_id
        elif governmentusertype_id:
            filters["governmentusertype_id_id"] = governmentusertype_id
        else:
            filters.update({
                "staffusertype_id__isnull": True,
                "contractorusertype_id__isnull": True,
                "governmentusertype_id__isnull": True,
            })
        return filters

    def _permission_payload(self, staff):
        filters = self._role_filters(staff)
        if not filters.get("usertype_id_id"):
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
        filters = self._role_filters(staff)
        if not filters.get("usertype_id_id"):
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
            .prefetch_related("location_nodes")
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
                "corporationId": staff.corporation_id,
                "municipalityId": staff.municipality_id,
                "townPanchayatId": staff.town_panchayat_id,
                "panchayatUnionId": staff.panchayat_union_id,
                "panchayatId": staff.panchayat_id,
                "localBodyLevel": local_body_level,
                "localBodyId": local_body_id,
                "depotId": None,
                "vehicleId": None,
            }

        local_body_pairs = (
            ("corporation_id", scope.corporation_id),
            ("municipality_id", scope.municipality_id),
            ("town_panchayat_id", scope.town_panchayat_id),
            ("panchayat_union_id", scope.panchayat_union_id),
            ("panchayat_id", scope.panchayat_id),
        )
        local_body_level, local_body_id = next(
            ((level, value) for level, value in local_body_pairs if value),
            (None, None),
        )
        return {
            "locationNodes": list(scope.location_nodes.values_list("unique_id", flat=True)),
            "stateId": scope.state_id,
            "districtId": scope.district_id,
            "areaTypeId": scope.area_type_id,
            "corporationId": scope.corporation_id,
            "municipalityId": scope.municipality_id,
            "townPanchayatId": scope.town_panchayat_id,
            "panchayatUnionId": scope.panchayat_union_id,
            "panchayatId": scope.panchayat_id,
            "localBodyLevel": local_body_level,
            "localBodyId": local_body_id,
            "depotId": scope.depot_id,
            "vehicleId": scope.vehicle_id,
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
                "mobileNumber": staff_payload.get("contact_mobile") or "",
                "officeEmail": staff_payload.get("contact_email") or "",
                "departmentId": staff_payload.get("department_id") or "",
                "designationId": staff_payload.get("designation_id") or "",
                "doj": staff_payload.get("doj") or "",
                "activeStatus": staff_payload.get("active_status", True),
            },
            "loginConfig": {
                "username": staff_payload.get("username") or "",
                "password": "",
                "confirmPassword": "",
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
