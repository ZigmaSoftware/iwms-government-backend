"""API tests for SubProperty endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/waste-types/subproperties/"


@pytest.mark.django_db
class TestSubPropertyAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSubPropertyAPICreate:
    def test_create_returns_success(self, auth_client):
        from app.models.masters.waste_masters.property import Property
        prop = Property.objects.create(property_name="Organic")
        resp = auth_client.post(
            BASE,
            {"property_id": prop.unique_id, "sub_property_name": "Food Waste"},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestSubPropertyAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}SPR-NOTEXIST/")
        assert resp.status_code in (404, 400)


@pytest.mark.django_db
class TestSubPropertyAPIUpdate:
    def test_patch_returns_success(self, auth_client):
        from app.models.masters.waste_masters.property import Property
        from app.models.masters.waste_masters.subproperty import SubProperty
        prop = Property.objects.create(property_name="Inorganic")
        sub = SubProperty.objects.create(property_id=prop, sub_property_name="Plastic")
        resp = auth_client.patch(
            f"{BASE}{sub.unique_id}/", {"sub_property_name": "Hard Plastic"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestSubPropertyAPIDelete:
    def test_delete_returns_success(self, auth_client):
        from app.models.masters.waste_masters.property import Property
        from app.models.masters.waste_masters.subproperty import SubProperty
        prop = Property.objects.create(property_name="Hazardous")
        sub = SubProperty.objects.create(property_id=prop, sub_property_name="Chemical")
        resp = auth_client.delete(f"{BASE}{sub.unique_id}/")
        assert resp.status_code in (200, 204)
