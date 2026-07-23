"""Unit tests for CollectionPointSerializer's nested Bins create/update/sync logic."""
import pytest

from app.models.masters.waste_masters.bins import Bins
from app.serializers.core_modules.schedule_setup.collection_point_serializer import CollectionPointSerializer


@pytest.fixture
def waste_type(db):
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
    return WasteType.objects.create(waste_type_name="Wet Waste")


@pytest.mark.django_db
class TestCollectionPointSerializerCollectionType:
    def test_defaults_to_bin_collection(self, district):
        payload = {
            "district_id": district.unique_id,
            "cp_name": "Default Type CP",
            "latitude": 13.05,
            "longitude": 80.25,
        }
        serializer = CollectionPointSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        collection_point = serializer.save()
        assert collection_point.collection_type == "bin_collection"

    def test_accepts_explicit_household_collection_type(self, district):
        payload = {
            "district_id": district.unique_id,
            "cp_name": "Household CP",
            "collection_type": "household_collection",
            "latitude": 13.05,
            "longitude": 80.25,
        }
        serializer = CollectionPointSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        collection_point = serializer.save()
        assert collection_point.collection_type == "household_collection"


@pytest.mark.django_db
class TestCollectionPointSerializerBins:
    def test_create_with_bins_creates_linked_bins(self, district, waste_type):
        payload = {
            "district_id": district.unique_id,
            "cp_name": "Test CP",
            "latitude": 13.05,
            "longitude": 80.25,
            "bins": [
                {"wastetype_id": waste_type.unique_id, "bin_name": "Bin A", "bin_capacity": 100, "bin_type": "small"},
                {"wastetype_id": waste_type.unique_id, "bin_name": "Bin B", "bin_capacity": 200, "bin_type": "medium"},
            ],
        }
        serializer = CollectionPointSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        collection_point = serializer.save()

        bins = Bins.objects.filter(collection_point_id=collection_point, is_deleted=False)
        assert bins.count() == 2
        assert set(bins.values_list("bin_name", flat=True)) == {"Bin A", "Bin B"}

    def test_update_with_shrunk_bins_soft_deletes_removed(self, district, waste_type):
        create_payload = {
            "district_id": district.unique_id,
            "cp_name": "Test CP 2",
            "latitude": 13.05,
            "longitude": 80.25,
            "bins": [
                {"wastetype_id": waste_type.unique_id, "bin_name": "Bin A", "bin_capacity": 100, "bin_type": "small"},
                {"wastetype_id": waste_type.unique_id, "bin_name": "Bin B", "bin_capacity": 200, "bin_type": "medium"},
            ],
        }
        serializer = CollectionPointSerializer(data=create_payload)
        assert serializer.is_valid(), serializer.errors
        collection_point = serializer.save()

        kept_bin = Bins.objects.get(collection_point_id=collection_point, bin_name="Bin A")

        update_payload = {
            "district_id": district.unique_id,
            "cp_name": "Test CP 2",
            "latitude": 13.05,
            "longitude": 80.25,
            "bins": [
                {
                    "unique_id": kept_bin.unique_id,
                    "wastetype_id": waste_type.unique_id,
                    "bin_name": "Bin A",
                    "bin_capacity": 150,
                    "bin_type": "large",
                },
            ],
        }
        update_serializer = CollectionPointSerializer(collection_point, data=update_payload)
        assert update_serializer.is_valid(), update_serializer.errors
        update_serializer.save()

        kept_bin.refresh_from_db()
        assert kept_bin.bin_capacity == 150
        assert kept_bin.bin_type == "large"
        assert kept_bin.is_deleted is False

        removed_bin = Bins.objects.get(collection_point_id=collection_point, bin_name="Bin B")
        assert removed_bin.is_deleted is True
        assert removed_bin.is_active is False

    def test_bins_detail_read_field_reflects_active_bins(self, district, waste_type):
        payload = {
            "district_id": district.unique_id,
            "cp_name": "Test CP 3",
            "latitude": 13.05,
            "longitude": 80.25,
            "bins": [
                {"wastetype_id": waste_type.unique_id, "bin_name": "Bin A", "bin_capacity": 100, "bin_type": "small"},
            ],
        }
        serializer = CollectionPointSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        collection_point = serializer.save()

        read_serializer = CollectionPointSerializer(collection_point)
        detail = read_serializer.data["bins_detail"]
        assert len(detail) == 1
        assert detail[0]["bin_name"] == "Bin A"
