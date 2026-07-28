"""API tests for CustomerCreation endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/customer-masters/customercreations/"


@pytest.fixture
def customer_payload(db, country, state, district, city, zone, ward):
    from app.models.masters.waste_masters.property import Property
    from app.models.masters.waste_masters.subproperty import SubProperty
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType

    prop = Property.objects.create(property_name="Residential")
    sub_prop = SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)
    waste_types = [
        WasteType.objects.create(waste_type_name="Wet Waste"),
        WasteType.objects.create(waste_type_name="Dry Waste"),
    ]

    return {
        "customer_name": "API Customer",
        "contact_no": "9876543210",
        "username": "api_customer",
        "email": "customer@example.com",
        "password": "Password123",
        "pincode": "600001",
        "latitude": "13.0827",
        "longitude": "80.2707",
        "sqft": "1200.50",
        "id_proof_type": "AADHAAR",
        "id_no": "1234-5678-9012",
        "country_id": country.unique_id,
        "state_id": state.unique_id,
        "district_id": district.unique_id,
        "city_id": city.unique_id,
        "zone_id": zone.unique_id,
        "ward_id": ward.unique_id,
        "property_id": prop.unique_id,
        "sub_property_id": sub_prop.unique_id,
        "apartment_name": "Sunrise Apt",
        "block_no": "A",
        "flat_no": "101",
        "waste_type_ids": [waste_type.unique_id for waste_type in waste_types],
    }


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


@pytest.mark.django_db
class TestCustomerAPIWasteTypes:
    def test_create_accepts_multiple_waste_type_ids(self, auth_client, customer_payload):
        resp = auth_client.post(BASE, customer_payload, format="json")

        assert resp.status_code in (200, 201), resp.json()
        data = resp.json()
        assert set(data["waste_type_ids"]) == set(customer_payload["waste_type_ids"])
        assert len(data["waste_types"]) == 2

    def test_patch_replaces_waste_type_ids(self, auth_client, customer_payload):
        from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType

        create_resp = auth_client.post(BASE, customer_payload, format="json")
        assert create_resp.status_code in (200, 201), create_resp.json()
        customer_id = create_resp.json()["unique_id"]

        dry_waste = WasteType.objects.get(waste_type_name="Dry Waste")
        patch_resp = auth_client.patch(
            f"{BASE}{customer_id}/",
            {"waste_type_ids": [dry_waste.unique_id]},
            format="json",
        )

        assert patch_resp.status_code in (200, 204), patch_resp.json() if patch_resp.content else None
        get_resp = auth_client.get(f"{BASE}{customer_id}/")
        assert get_resp.status_code == 200
        assert get_resp.json()["waste_type_ids"] == [dry_waste.unique_id]
