"""API tests for audit log endpoints."""
import pytest

AUDIT_BASE = "/api/v1/audits/common-audit/"
LOGIN_AUDIT_BASE = "/api/v1/audits/login-audit/"


@pytest.mark.django_db
class TestCommonAuditAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(AUDIT_BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(AUDIT_BASE)
        assert resp.status_code == 200

    def test_create_uses_authenticated_user(self, auth_client):
        resp = auth_client.post(
            AUDIT_BASE,
            {
                "module_name": "masters",
                "endpoint_name": "wards",
                "method": "DOWNLOAD",
                "createdBy": "spoofed-user",
                "new_data": {"action": "download_template"},
            },
            format="json",
        )

        assert resp.status_code == 201
        assert resp.data["createdBy"] != "spoofed-user"
        assert resp.data["new_data"]["action"] == "download_template"


@pytest.mark.django_db
class TestLoginAuditAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(LOGIN_AUDIT_BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(LOGIN_AUDIT_BASE)
        assert resp.status_code == 200
