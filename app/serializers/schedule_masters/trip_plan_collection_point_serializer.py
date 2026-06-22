from rest_framework import serializers

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import HIERARCHY_FIELDS, hierarchy_payload, selected_hierarchy_values


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
    local_body = serializers.SerializerMethodField()

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
            "local_body",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
            "hierarchy",
            "sequence",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
            "created_at",
            "updated_at",
        ]
        validators = []

    hierarchy = serializers.SerializerMethodField()

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        if not cp:
            return None
        return {
            "unique_id": cp.unique_id,
            "cp_name": cp.cp_name,
            "latitude": cp.latitude,
            "longitude": cp.longitude,
            **hierarchy_payload(cp),
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
            **hierarchy_payload(c),
        }

    def get_hierarchy(self, obj):
        return hierarchy_payload(obj)

    def get_local_body(self, obj):
        local_bodies = [
            ("corporation_id", "Corporation", "corporation_name"),
            ("municipality_id", "Municipality", "municipality_name"),
            ("town_panchayat_id", "Town Panchayat", "town_panchayat_name"),
            ("panchayat_union_id", "Panchayat Union", "union_name"),
            ("panchayat_id", "Panchayat / PLB", "panchayat_name"),
        ]
        for field, label, name_attr in local_bodies:
            value = getattr(obj, field, None)
            if value:
                return {
                    "field": field,
                    "label": label,
                    "unique_id": getattr(value, "unique_id", None),
                    "name": getattr(value, name_attr, None),
                }
        return None

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
        trip_plan = attrs.get("trip_plan_id", getattr(instance, "trip_plan_id", None))
        if trip_plan and collection_type != trip_plan.collection_type:
            raise serializers.ValidationError(
                {"collection_type": "Trip point collection type must match the selected Trip Plan."}
            )

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
        elif collection_type in {
            TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
            TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
        }:
            selected_hierarchy = selected_hierarchy_values(trip_plan) if trip_plan else {}
            if not customer and not selected_hierarchy:
                raise serializers.ValidationError(
                    {
                        "customer_id": (
                            "Select a customer or use a trip plan assigned to Corporation, "
                            "Municipality, Town Panchayat, Panchayat Union or Panchayat."
                        )
                    }
                )
            attrs["collection_point_id"] = None
            attrs["bin_id"] = None

        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._copy_trip_plan_hierarchy(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._copy_trip_plan_hierarchy(instance)
        return instance

    def _copy_trip_plan_hierarchy(self, instance):
        if instance.collection_type not in {
            TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
            TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
        }:
            return
        if instance.customer_id_id:
            return
        trip_plan = instance.trip_plan_id
        updates = []
        for field in HIERARCHY_FIELDS:
            value = getattr(trip_plan, field, None)
            if getattr(instance, field) != value:
                setattr(instance, field, value)
                updates.append(field)
        if updates:
            instance.save(update_fields=updates)
