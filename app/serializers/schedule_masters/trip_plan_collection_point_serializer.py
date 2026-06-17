from rest_framework import serializers

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


class TripPlanCollectionPointSerializer(
    
    serializers.ModelSerializer,
):
    trip_plan_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=TripPlan.objects.filter(is_deleted=False),
    )
    collection_point_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Collection_point.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    bin_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Bins.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    customer_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    collection_point = serializers.SerializerMethodField()
    bin = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()

    class Meta:
        model = TripPlanCollectionPoint
        fields = [
            "unique_id",
            "trip_plan_id",
            "collection_type",
            "collection_point_id",
            "collection_point",
            "bin_id",
            "bin",
            "customer_id",
            "customer",
            "zone_id",
            "ward_id",
            "panchayat_id",
            "sequence",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "zone_id",
            "ward_id",
            "panchayat_id",
            "created_at",
            "updated_at",
        ]
        validators = []

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        if not cp:
            return None
        return {
            "unique_id": cp.unique_id,
            "cp_name": cp.cp_name,
            "latitude": cp.latitude,
            "longitude": cp.longitude,
            "panchayat_id": getattr(cp.panchayat_id, "unique_id", None),
            "panchayat_name": getattr(cp.panchayat_id, "panchayat_name", None),
            "ward_id": getattr(cp.ward_id, "unique_id", None),
            "ward_name": getattr(cp.ward_id, "ward_name", None),
            "zone_id": getattr(getattr(cp.ward_id, "zone_id", None), "unique_id", None),
            "zone_name": getattr(getattr(cp.ward_id, "zone_id", None), "zone_name", None),
        }

    def get_bin(self, obj):
        bin_obj = obj.bin_id
        if not bin_obj:
            return None
        return {
            "unique_id": bin_obj.unique_id,
            "bin_name": bin_obj.bin_name,
            "bin_capacity": bin_obj.bin_capacity,
            "bin_type": bin_obj.bin_type,
        }

    def get_customer(self, obj):
        c = obj.customer_id
        if not c:
            return None
        return {
            "unique_id": c.unique_id,
            "customer_name": c.customer_name,
            "ward_name": getattr(c.ward, "ward_name", None) if hasattr(c, "ward") else None,
            "zone_name": getattr(c.zone, "zone_name", None) if hasattr(c, "zone") else None,
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        collection_type = attrs.get(
            "collection_type",
            getattr(instance, "collection_type", TripPlanCollectionPoint.COLLECTION_TYPE_BIN),
        )
        collection_point = attrs.get(
            "collection_point_id",
            getattr(instance, "collection_point_id", None),
        )
        bin_obj = attrs.get("bin_id", getattr(instance, "bin_id", None))
        customer = attrs.get("customer_id", getattr(instance, "customer_id", None))

        if collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
            if not collection_point:
                raise serializers.ValidationError(
                    {"collection_point_id": "Collection point is required for bin collection."}
                )
            if not bin_obj:
                raise serializers.ValidationError(
                    {"bin_id": "Bin is required for bin collection."}
                )
            if bin_obj and collection_point and bin_obj.collection_point_id != collection_point:
                raise serializers.ValidationError(
                    {"bin_id": "Selected bin does not belong to the collection point."}
                )
        elif collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD:
            if not customer:
                raise serializers.ValidationError(
                    {"customer_id": "Customer is required for household collection."}
                )

        return attrs
