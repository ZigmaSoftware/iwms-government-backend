from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.models.superadmin_masters.auth_user import User


class DashboardSummaryAlertsAPITest(APITestCase):
    url = "/api/v1/dashboard/summary/"

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="dashboard_alert_admin",
            password="testpass123",
        )
        token = AccessToken.for_user(self.superuser)
        token["unique_id"] = self.superuser.unique_id
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_summary_exposes_combined_critical_alert_contract(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("critical_alerts", response.data)
        self.assertEqual(response.data["critical_alerts"], [])
        self.assertIn("breakdown", response.data["vehicle_status_detail"])

