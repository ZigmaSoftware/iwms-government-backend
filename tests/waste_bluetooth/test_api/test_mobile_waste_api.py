"""Regression tests for the mobile waste collection endpoint."""
import pytest

from app.models.user_creations.waste_collection_bluetooth import (
    WasteCollectionMain,
    WasteCollectionSub,
)


BASE = "/api/v1/waste/"


@pytest.mark.django_db
class TestMobileWasteFinalize:
    def test_finalize_uses_current_collection_models(self, auth_client):
        WasteCollectionSub.objects.create(
            screen_unique_id="screen-1",
            customer_id="customer-1",
            waste_type_id="1",
            weight=1.25,
        )
        WasteCollectionSub.objects.create(
            screen_unique_id="screen-1",
            customer_id="customer-1",
            waste_type_id="2",
            weight=2.75,
        )

        resp = auth_client.post(
            f"{BASE}finalize-waste/",
            {
                "screen_unique_id": "screen-1",
                "customer_id": "customer-1",
                "entry_type": "app",
            },
            format="json",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["total_weight"] == 4.0

        main = WasteCollectionMain.objects.get(unique_id=data["main_unique_id"])
        assert main.customer_id == "customer-1"
        assert main.total_waste_collected == 4.0
        assert set(
            WasteCollectionSub.objects.filter(
                screen_unique_id="screen-1",
                customer_id="customer-1",
            ).values_list("form_unique_id", flat=True)
        ) == {main.unique_id}

    def test_finalize_without_sub_records_returns_error(self, auth_client):
        resp = auth_client.post(
            f"{BASE}finalize-waste/",
            {"screen_unique_id": "screen-2", "customer_id": "customer-1"},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
