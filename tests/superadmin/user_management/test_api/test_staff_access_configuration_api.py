from unittest.mock import patch

from django.db import IntegrityError
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.screen_management.companyuserscreenpermission import UserScreenPermission
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.mainscreentype import MainScreenType
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.models.superadmin_masters.auth_user import User
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope


class StaffAccessConfigurationAPITest(APITestCase):
    url = "/api/v1/user-creations/staff-access-configuration/"
    preview_url = "/api/v1/user-creations/staff-access-configuration/preview/"
    scope_admins_url = "/api/v1/user-creations/staff-access-configuration/scope-admins/"

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="staff_access_admin",
            password="testpass123",
        )
        token = AccessToken.for_user(self.superuser)
        token["unique_id"] = self.superuser.unique_id
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.user_type = UserType.objects.create(name="Staff Access")
        self.staff_user_type = StaffUserType.objects.create(
            usertype_id=self.user_type,
            name="company_admin",
        )
        self.main_screen_type = MainScreenType.objects.create(type_name="Admin")
        self.main_screen = MainScreen.objects.create(
            mainscreentype_id=self.main_screen_type,
            mainscreen_name="Staff Module",
            icon_name="staff-module",
            order_no=1,
        )
        self.user_screen = UserScreen.objects.create(
            mainscreen_id=self.main_screen,
            userscreen_name="Staff Access",
            folder_name="staff-access",
            icon_name="staff-access",
            order_no=1,
        )
        self.action = UserScreenAction.objects.create(
            action_name="view",
            variable_name="view",
        )
        self.column = UserScreenColumn.objects.create(
            userscreen_id=self.user_screen,
            field_name="employee_name",
            display_name="Employee Name",
            data_type="string",
            db_column="employee_name",
            order_no=1,
        )

    def payload(self, username="staff.access"):
        return {
            "basicInfo": {
                "employee_name": "Staff Access User",
                "active_status": True,
            },
            "loginConfig": {
                "username": username,
                "password": "Secret123!",
                "confirmPassword": "Secret123!",
                "userTypeId": self.user_type.unique_id,
                "staffUserTypeId": self.staff_user_type.unique_id,
                "accountStatus": "ACTIVE",
            },
            "permissions": [
                {
                    "mainScreenId": self.main_screen.unique_id,
                    "userScreens": [
                        {
                            "userScreenId": self.user_screen.unique_id,
                            "actionIds": [self.action.unique_id],
                            "columnIds": [self.column.unique_id],
                        }
                    ],
                }
            ],
            "dashboardPermissions": [
                {
                    "widgetName": "trip_summary",
                    "isEnabled": True,
                    "orderNo": 1,
                }
            ],
            "dataScope": {
                "locationNodes": [],
                "depotId": None,
                "vehicleId": None,
            },
        }

    def test_happy_path_creates_staff_and_permission_rows(self):
        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            Staffcreation.objects.filter(username="staff.access").exists()
        )
        self.assertTrue(
            UserScreenPermission.objects.filter(
                staffusertype_id=self.staff_user_type,
                userscreen_id=self.user_screen,
                userscreenaction_id=self.action,
                is_deleted=False,
            ).exists()
        )

    def test_permission_integrity_error_rolls_back_staff_creation(self):
        with patch(
            "app.serializers.superadmin.staff_management.staff_access_configuration_serializer."
            "UserScreenPermissionMultiScreenSerializer.save",
            side_effect=IntegrityError("permission failed"),
        ):
            response = self.client.post(
                self.url,
                self.payload(username="rollback.staff"),
                format="json",
            )

        self.assertGreaterEqual(response.status_code, 400)
        self.assertFalse(
            Staffcreation.objects.filter(username="rollback.staff").exists()
        )

    def test_preview_validates_without_writing_rows(self):
        response = self.client.post(
            self.preview_url,
            self.payload(username="preview.staff"),
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(
            Staffcreation.objects.filter(username="preview.staff").exists()
        )
        self.assertFalse(
            UserScreenPermission.objects.filter(
                staffusertype_id=self.staff_user_type,
                userscreen_id=self.user_screen,
            ).exists()
        )

    def test_password_mismatch_returns_confirm_password_error(self):
        payload = self.payload(username="bad.password")
        payload["loginConfig"]["confirmPassword"] = "Different123!"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("confirmPassword", response.data)

    def _scope_admin_fixture(self):
        continent = Continent.objects.create(name="Asia")
        country = Country.objects.create(
            continent_id=continent,
            name="India",
            currency="INR",
            mob_code="+91",
        )
        state = State.objects.create(
            continent_id=continent,
            country_id=country,
            name="Tamil Nadu",
            label="TN",
        )
        district = District.objects.create(
            continent_id=continent,
            country_id=country,
            state_id=state,
            name="Scope District",
        )
        other_district = District.objects.create(
            continent_id=continent,
            country_id=country,
            state_id=state,
            name="Outside District",
        )
        area_type = AreaType.objects.create(
            state_id=state,
            district_id=district,
            name="Rural Local Body",
        )
        admin_role = GovernmentStaffUserType.objects.create(
            usertype_id=self.user_type,
            name="govt_district_admin",
            level="district",
        )
        operator_role = GovernmentStaffUserType.objects.create(
            usertype_id=self.user_type,
            name="govt_panchayat_operator",
            level="panchayat",
        )
        scope_admin = Staffcreation.objects.create(
            employee_name="District Admin",
            username="district.scope.admin",
            governmentusertype_id=admin_role,
            state=state,
            district=district,
            active_status=True,
            login_enabled=True,
        )
        StaffDataScope.objects.create(
            staff=scope_admin,
            state=state,
            district=district,
        )
        return state, district, other_district, area_type, scope_admin, operator_role

    def test_scope_admin_list_includes_name_and_hierarchy(self):
        _, district, _, _, scope_admin, _ = self._scope_admin_fixture()

        response = self.client.get(self.scope_admins_url)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data[0]["id"], scope_admin.staff_unique_id)
        self.assertEqual(response.data[0]["name"], "District Admin")
        self.assertEqual(response.data[0]["hierarchy"][-1]["id"], district.unique_id)

    def test_child_scope_cannot_escape_selected_admin_district(self):
        state, _, outside, _, scope_admin, operator_role = self._scope_admin_fixture()
        payload = self.payload(username="outside.scope")
        payload["basicInfo"]["staff_head_id"] = scope_admin.staff_unique_id
        payload["loginConfig"]["governmentUserTypeId"] = operator_role.unique_id
        payload["permissions"] = []
        payload["dashboardPermissions"] = []
        payload["dataScope"] = {
            "locationNodes": [],
            "stateId": state.unique_id,
            "districtId": outside.unique_id,
            "areaTypeId": None,
            "corporationIds": [],
            "municipalityIds": [],
            "townPanchayatIds": [],
            "panchayatUnionIds": [],
            "panchayatIds": [],
            "wardIds": [],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("dataScope", response.data)
        self.assertFalse(Staffcreation.objects.filter(username="outside.scope").exists())

    def test_child_is_linked_to_admin_and_saved_inside_hierarchy(self):
        state, district, _, area_type, scope_admin, operator_role = self._scope_admin_fixture()
        panchayat = Panchayat.objects.create(
            state_id=state,
            district_id=district,
            area_type_id=area_type,
            panchayat_name="Scope Panchayat",
        )
        payload = self.payload(username="inside.scope")
        payload["basicInfo"]["staff_head_id"] = scope_admin.staff_unique_id
        payload["loginConfig"]["governmentUserTypeId"] = operator_role.unique_id
        payload["permissions"] = []
        payload["dashboardPermissions"] = []
        payload["dataScope"] = {
            "locationNodes": [],
            "stateId": state.unique_id,
            "districtId": district.unique_id,
            "areaTypeId": area_type.unique_id,
            "corporationIds": [],
            "municipalityIds": [],
            "townPanchayatIds": [],
            "panchayatUnionIds": [],
            "panchayatIds": [panchayat.unique_id],
            "wardIds": [],
        }

        with patch(
            "app.viewsets.superadmin.staff_management."
            "staff_access_configuration_viewset.StaffAccessConfigurationViewSet.log_audit"
        ):
            response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        child = Staffcreation.objects.get(username="inside.scope")
        self.assertEqual(child.staff_head_id, scope_admin.staff_unique_id)
        self.assertEqual(child.staff_head, scope_admin.employee_name)
        self.assertEqual(child.district_id, district.unique_id)
        self.assertEqual(child.panchayat_id, panchayat.unique_id)
