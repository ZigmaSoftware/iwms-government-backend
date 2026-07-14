"""Regression tests for the mobile waste collection endpoint."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from app.models.user_creations.waste_collection_bluetooth import (
    WasteCollectionMain,
    WasteCollectionSub,
)


BASE = "/api/v1/waste/"


@pytest.mark.django_db
class TestMobileWasteFinalize:
    def test_insert_waste_sub_stamps_explicit_id_and_weight(self, auth_client):
        image = SimpleUploadedFile(
            "waste.jpg",
            b"fake image bytes",
            content_type="image/jpeg",
        )

        resp = auth_client.post(
            f"{BASE}insert-waste-sub/",
            {
                "screen_unique_id": "screen-insert-1",
                "customer_id": "customer-1",
                "waste_type": "wst-wet",
                "weight": "2.50",
                "latitude": "10.1",
                "longitude": "76.2",
                "image": image,
            },
            format="multipart",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["unique_id"].startswith("wcs-")

        row = WasteCollectionSub.objects.get(unique_id=data["unique_id"])
        assert row.waste_type_id == "wst-wet"
        assert row.weight == 2.5

    def test_insert_waste_sub_continues_when_image_dir_not_writable(
        self,
        auth_client,
        monkeypatch,
    ):
        def deny_upload(_image):
            raise PermissionError("media directory is not writable")

        monkeypatch.setattr(
            "app.viewsets.waste_collection_bluetooth.waste_bluetooth_viewset.upload_image",
            deny_upload,
        )

        image = SimpleUploadedFile(
            "waste.jpg",
            b"fake image bytes",
            content_type="image/jpeg",
        )

        resp = auth_client.post(
            f"{BASE}insert-waste-sub/",
            {
                "screen_unique_id": "screen-insert-2",
                "customer_id": "customer-1",
                "waste_type": "wst-dry",
                "weight": "3.75",
                "image": image,
            },
            format="multipart",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["image"] == ""
        assert "Image could not be saved" in data["image_warning"]

        row = WasteCollectionSub.objects.get(unique_id=data["unique_id"])
        assert row.weight == 3.75
        assert row.image == ""

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
        assert main.unique_id.startswith("wcm-")
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
