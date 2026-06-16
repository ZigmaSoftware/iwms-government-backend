"""API tests for WasteType (assets) endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/assets/waste-types/"


@pytest.mark.django_db
class TestWasteTypeAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWasteTypeAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(
            BASE,
            {"waste_type_name": "Electronic Waste"},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestWasteTypeAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}WT-NOTEXIST/")
        assert resp.status_code in (404, 400)


@pytest.mark.django_db
class TestWasteTypeAPIUpdate:
    def test_patch_returns_success(self, auth_client):
        from app.models.user_creations.waste_collection_bluetooth import WasteType
        wt = WasteType.objects.create(waste_type_name="Mixed Waste")
        resp = auth_client.patch(
            f"{BASE}{wt.pk}/", {"waste_type_name": "Mixed Recyclable Waste"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestWasteTypeAPIDelete:
    def test_delete_returns_success(self, auth_client):
        from app.models.user_creations.waste_collection_bluetooth import WasteType
        wt = WasteType.objects.create(waste_type_name="Temp Waste")
        resp = auth_client.delete(f"{BASE}{wt.pk}/")
        assert resp.status_code in (200, 204)
