"""API tests for CustomerCreation endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/customer-masters/customercreations/"


@pytest.mark.django_db
class TestCustomerAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCustomerAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}CUS-NOTEXIST/")
        assert resp.status_code in (404, 400)
