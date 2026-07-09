from unittest.mock import patch

from django.db import IntegrityError
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.models.superadmin_masters.auth_user import User
from app.models.user_creations.staffcreation import Staffcreation


class StaffAccessConfigurationAPITest(APITestCase):
    url = "/api/v1/user-creations/staff-access-configuration/"
    preview_url = "/api/v1/user-creations/staff-access-configuration/preview/"

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
            "app.serializers.user_creations.staff_access_configuration_serializer."
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
