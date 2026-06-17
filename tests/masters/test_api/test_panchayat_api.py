"""API tests for Panchayat endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/panchayat/"


@pytest.mark.django_db
class TestPanchayatAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPanchayatAPICreate:
    def test_create_returns_success(self, auth_client, state, city, district):
        resp = auth_client.post(
            BASE,
            {
                "state_id": state.unique_id,
                "city_id": city.unique_id,
                "district_id": district.unique_id,
                "panchayat_name": "Test Panchayat",
                "agreed_weight_kg": "2500.75",
                "weight_unit": "kg",
                "effective_from": "2026-05-01",
                "geofencing_type": "polygon",
                "coordinates": [
                    {"latitude": 12.9871, "longitude": 80.2184},
                    {"latitude": 12.9912, "longitude": 80.2253},
                    {"latitude": 12.9846, "longitude": 80.2311},
                ],
            },
            format="json",
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["agreed_weight_kg"] == "2500.75"
        assert data["weight_unit"] == "kg"
        assert data["effective_from"] == "2026-05-01"
        assert len(data["coordinates"]) == 3


@pytest.mark.django_db
class TestPanchayatAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, state, city, district):
        from app.models.masters.panchayat import Panchayat
        p = Panchayat.objects.create(
            state_id=state, city_id=city, district_id=district,
            panchayat_name="Sample Panchayat",
            geofencing_type="circle",
        )
        resp = auth_client.get(f"{BASE}{p.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPanchayatAPIUpdate:
    def test_patch_returns_success(self, auth_client, state, city, district):
        from app.models.masters.panchayat import Panchayat
        p = Panchayat.objects.create(
            state_id=state, city_id=city, district_id=district,
            panchayat_name="Old Name",
            geofencing_type="square",
        )
        resp = auth_client.patch(
            f"{BASE}{p.unique_id}/",
            {
                "panchayat_name": "New Name",
                "agreed_weight_kg": "125.25",
                "weight_unit": "tonne",
                "effective_from": "2026-06-01",
                "coordinates": [
                    [12.9801, 80.2201],
                    [12.9851, 80.2251],
                    [12.9811, 80.2291],
                ],
            },
            format="json"
        )
        assert resp.status_code in (200, 204)
        p.refresh_from_db()
        assert str(p.agreed_weight_kg) == "125.25"
        assert p.weight_unit == "tonne"
        assert str(p.effective_from) == "2026-06-01"
        assert len(p.coordinates) == 3


@pytest.mark.django_db
class TestPanchayatAPIDelete:
    def test_delete_returns_success(self, auth_client, state, city, district):
        from app.models.masters.panchayat import Panchayat
        p = Panchayat.objects.create(
            state_id=state, city_id=city, district_id=district,
            panchayat_name="Delete Me",
            geofencing_type="rectangle",
        )
        resp = auth_client.delete(f"{BASE}{p.unique_id}/")
        assert resp.status_code in (200, 204)
