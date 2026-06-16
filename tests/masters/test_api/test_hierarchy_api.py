"""API tests for AdministrativeHierarchy endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/hierarchy/"


@pytest.fixture
def area_type_obj(db, state, city, district):
    from app.models.masters.areatype import AreaType
    return AreaType.objects.create(
        name="Rural", state_id=state, city_id=city, district_id=district
    )


@pytest.mark.django_db
class TestHierarchyAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestHierarchyAPICreate:
    def test_create_returns_success(self, auth_client, area_type_obj):
        resp = auth_client.post(
            BASE,
            {
                "area_type": area_type_obj.unique_id,
                "level_name": "Ward",
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestHierarchyAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, area_type_obj):
        from app.models.masters.hierarchy import AdministrativeHierarchy
        hier = AdministrativeHierarchy.objects.create(
            area_type=area_type_obj, level_name="Zone"
        )
        resp = auth_client.get(f"{BASE}{hier.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestHierarchyAPIUpdate:
    def test_patch_returns_success(self, auth_client, area_type_obj):
        from app.models.masters.hierarchy import AdministrativeHierarchy
        hier = AdministrativeHierarchy.objects.create(
            area_type=area_type_obj, level_name="Panchayat"
        )
        resp = auth_client.patch(
            f"{BASE}{hier.unique_id}/", {"level_name": "Village"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestHierarchyAPIDelete:
    def test_delete_returns_success(self, auth_client, area_type_obj):
        from app.models.masters.hierarchy import AdministrativeHierarchy
        hier = AdministrativeHierarchy.objects.create(
            area_type=area_type_obj, level_name="Block"
        )
        resp = auth_client.delete(f"{BASE}{hier.unique_id}/")
        assert resp.status_code in (200, 204)
