from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.superadmin_masters.auth_user import User
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.user_management.staff_data_scope import StaffDataScope
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails


class StaffAccessDashboardAPITest(APITestCase):
    url = "/api/v1/user-creations/staff-access-dashboard/"

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="staff_dashboard_admin",
            password="testpass123",
        )
        token = AccessToken.for_user(self.superuser)
        token["unique_id"] = self.superuser.unique_id
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_authentication_is_required(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_empty_dashboard_has_stable_contract(self):
        response = self.client.get(self.url, {"scope_type": "corporation"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["access_context"]["locked"])
        self.assertEqual(response.data["summary"]["total_staff"], 0)
        self.assertEqual(response.data["scope_rows"], [])
        self.assertIn("assignment_kpis", response.data)
        self.assertIn("vehicle_performance", response.data)
        self.assertIn("trip_performance", response.data)
        self.assertIn("team_performance", response.data)

    def test_invalid_scope_type_is_rejected(self):
        response = self.client.get(self.url, {"scope_type": "municipality"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("scope_type", response.data)

    def test_invalid_date_range_is_rejected(self):
        response = self.client.get(
            self.url,
            {
                "scope_type": "corporation",
                "date_from": "2026-02-10",
                "date_to": "2026-02-01",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.data)

    def test_unknown_scope_is_rejected(self):
        response = self.client.get(
            self.url,
            {"scope_type": "corporation", "scope_id": "CORP-DOES-NOT-EXIST"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("scope_id", response.data)

    def test_selected_corporation_only_counts_its_staff(self):
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
            name="Dashboard District",
        )
        area_type = AreaType.objects.create(
            state_id=state,
            district_id=district,
            name="Urban Local Body",
        )
        selected = Corporation.objects.create(
            state_id=state,
            district_id=district,
            area_type_id=area_type,
            corporation_name="Selected Corporation",
        )
        other = Corporation.objects.create(
            state_id=state,
            district_id=district,
            area_type_id=area_type,
            corporation_name="Other Corporation",
        )
        StaffcreationOfficeDetails.objects.create(
            employee_name="Selected Staff",
            state=state,
            district=district,
            area_type=area_type,
            corporation=selected,
            active_status=True,
            login_enabled=True,
        )
        StaffcreationOfficeDetails.objects.create(
            employee_name="Other Staff",
            state=state,
            district=district,
            area_type=area_type,
            corporation=other,
            active_status=False,
        )

        response = self.client.get(
            self.url,
            {"scope_type": "corporation", "scope_id": selected.unique_id},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["selected_scope"]["id"], selected.unique_id)
        self.assertEqual(response.data["summary"]["total_staff"], 1)
        self.assertEqual(response.data["summary"]["active_staff"], 1)
        self.assertEqual(
            [row["name"] for row in response.data["staff_rows"]["results"]],
            ["Selected Staff"],
        )
        self.assertEqual(
            response.data["staff_rows"]["results"][0]["hierarchy_level"],
            "corporation",
        )
        self.assertEqual(
            response.data["staff_rows"]["results"][0]["hierarchy_names"],
            ["Selected Corporation"],
        )

        district_response = self.client.get(
            self.url,
            {"scope_type": "district", "scope_id": district.unique_id},
        )
        self.assertEqual(district_response.status_code, 200, district_response.data)
        self.assertEqual(
            district_response.data["selected_scope"]["scope_type"],
            "district",
        )
        self.assertEqual(district_response.data["summary"]["total_staff"], 2)

        active_response = self.client.get(
            self.url,
            {
                "scope_type": "district",
                "scope_id": district.unique_id,
                "status": "active",
            },
        )
        self.assertEqual(active_response.status_code, 200, active_response.data)
        self.assertEqual(active_response.data["summary"]["total_staff"], 1)

        multi_status_response = self.client.get(
            self.url,
            {
                "scope_type": "district",
                "scope_id": district.unique_id,
                "status": "active,inactive",
            },
        )
        self.assertEqual(
            multi_status_response.status_code,
            200,
            multi_status_response.data,
        )
        self.assertEqual(
            multi_status_response.data["summary"]["total_staff"],
            2,
        )

    def test_admin_filter_returns_only_that_admin_hierarchy(self):
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
            name="Admin District",
        )
        area_type = AreaType.objects.create(
            state_id=state,
            district_id=district,
            name="Urban Local Body",
        )
        corporation = Corporation.objects.create(
            state_id=state,
            district_id=district,
            area_type_id=area_type,
            corporation_name="Admin Corporation",
        )
        other_district = District.objects.create(
            continent_id=continent,
            country_id=country,
            state_id=state,
            name="Salem",
        )
        other_area_type = AreaType.objects.create(
            state_id=state,
            district_id=other_district,
            name="Other Urban Local Body",
        )
        other_corporation = Corporation.objects.create(
            state_id=state,
            district_id=other_district,
            area_type_id=other_area_type,
            corporation_name="Salem Corporation",
        )
        user_type = UserType.objects.create(name="Government")
        admin_role = GovernmentStaffUserType.objects.create(
            usertype_id=user_type,
            name="govt_district_admin",
            level="district",
        )
        admin = StaffcreationOfficeDetails.objects.create(
            employee_name="Erode District Admin",
            username="erode.admin",
            governmentusertype_id=admin_role,
            state=state,
            district=district,
            active_status=True,
            login_enabled=True,
        )
        admin_scope = StaffDataScope.objects.create(
            staff=admin,
            state=state,
            district=district,
        )
        # Even if legacy scope data contains a sibling District body, selecting
        # Admin Corporation must render only its effective hierarchy path.
        admin_scope.corporations.add(corporation, other_corporation)
        other_admin = StaffcreationOfficeDetails.objects.create(
            employee_name="Salem District Admin",
            username="salem.admin",
            governmentusertype_id=admin_role,
            state=state,
            district=other_district,
            active_status=True,
            login_enabled=True,
        )
        StaffDataScope.objects.create(
            staff=other_admin,
            state=state,
            district=other_district,
        )
        child = StaffcreationOfficeDetails.objects.create(
            employee_name="Admin Managed Staff",
            staff_head_id=admin.staff_unique_id,
            staff_head=admin.employee_name,
            state=state,
            district=district,
            area_type=area_type,
            corporation=corporation,
            active_status=True,
            login_enabled=True,
        )
        StaffcreationOfficeDetails.objects.create(
            employee_name="Other Admin Staff",
            state=state,
            district=district,
            area_type=area_type,
            corporation=corporation,
            active_status=True,
            login_enabled=True,
        )

        response = self.client.get(
            self.url,
            {
                "admin_id": admin.staff_unique_id,
                "scope_type": "corporation",
                "scope_id": corporation.unique_id,
            },
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["selected_admin"]["name"], admin.employee_name)
        self.assertEqual(
            response.data["selected_admin"]["hierarchy_label"],
            "Tamil Nadu → Admin District → Admin Corporation",
        )
        self.assertNotIn(
            "Salem",
            response.data["selected_admin"]["hierarchy_label"],
        )
        self.assertEqual(
            [item["id"] for item in response.data["filters"]["admins"]],
            [admin.staff_unique_id],
        )
        self.assertEqual(response.data["summary"]["total_staff"], 2)
        self.assertEqual(
            {
                row["staff_id"]
                for row in response.data["staff_rows"]["results"]
            },
            {admin.staff_unique_id, child.staff_unique_id},
        )

        # A logged-in District Admin cannot replace Erode with Salem through
        # query parameters; their Staff Access Configuration is authoritative.
        admin_scope.corporations.clear()
        self.client.force_authenticate(user=admin)
        locked_response = self.client.get(
            self.url,
            {
                "admin_id": other_admin.staff_unique_id,
                "scope_type": "district",
                "scope_id": other_district.unique_id,
            },
        )
        self.assertEqual(
            locked_response.status_code,
            200,
            locked_response.data,
        )
        self.assertTrue(locked_response.data["access_context"]["locked"])
        self.assertEqual(
            locked_response.data["access_context"]["admin_id"],
            admin.staff_unique_id,
        )
        self.assertEqual(
            locked_response.data["selected_scope"]["id"],
            district.unique_id,
        )
        self.assertEqual(
            locked_response.data["selected_admin"]["id"],
            admin.staff_unique_id,
        )
