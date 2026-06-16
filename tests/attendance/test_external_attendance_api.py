from unittest.mock import Mock, patch

import pytest


BASE = "/api/v1/attendance/external-records/"


@pytest.mark.django_db
class TestExternalAttendanceAPI:
    def test_company_id_is_required_for_platform_superuser(self, auth_client):
        response = auth_client.get(BASE)
        assert response.status_code == 400

    def test_project_id_is_required(self, auth_client, company):
        response = auth_client.get(BASE, {"company_id": company.unique_id})
        assert response.status_code == 400

    def test_unconfigured_project_returns_400(self, auth_client, company, project):
        response = auth_client.get(
            BASE,
            {"company_id": company.unique_id, "project_id": project.unique_id},
        )
        assert response.status_code == 400

    @patch("app.viewsets.attendance_view.external_attendance.requests.get")
    def test_proxies_dates_and_project_key(self, requests_get, auth_client, company, project):
        project.attendance_api_url = "http://zigfly.in/attendance-api/api/sync/recognized"
        project.attendance_api_key = "ZIGFLY_SYNC_2025"
        project.save(update_fields=["attendance_api_url", "attendance_api_key"])

        upstream = Mock()
        upstream.json.return_value = {
            "records": [{"emp_id": "EMP-1", "name": "Test Staff"}]
        }
        upstream.raise_for_status.return_value = None
        requests_get.return_value = upstream

        response = auth_client.get(
            BASE,
            {
                "company_id": company.unique_id,
                "project_id": project.unique_id,
                "from_date": "2026-06-15",
                "to_date": "2026-06-15",
            },
        )

        assert response.status_code == 200
        assert response.json()["count"] == 1
        requests_get.assert_called_once_with(
            project.attendance_api_url,
            params={"from_date": "2026-06-15", "to_date": "2026-06-15"},
            headers={
                "X-API-KEY": "ZIGFLY_SYNC_2025",
                "User-Agent": "CronSync/1.0",
                "Accept": "application/json",
            },
            timeout=30,
        )
