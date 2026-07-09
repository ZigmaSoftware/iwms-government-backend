from rest_framework import serializers

from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import flat_geo_display


class DailyTripHouseholdCollectionSerializer(
    
    serializers.ModelSerializer,
):
    trip_assignment_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    customer_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.filter(is_deleted=False),
    )

    trip_assignment = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    hierarchy = serializers.SerializerMethodField()

    class Meta:
        model = DailyTripHouseholdCollection
        fields = [
            "unique_id",
            "trip_assignment_id",
            "trip_assignment",
            "customer_id",
            "customer",
            "collection_type",
            "waste_collection_id",
            "hierarchy",
            "sequence",
            "is_collected",
            "collected_at",
            "collected_weight_kg",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "waste_collection_id",
            "created_at",
            "updated_at",
        ]

    def get_trip_assignment(self, obj):
        assignment = obj.trip_assignment_id
        if not assignment:
            return None
        trip_plan = getattr(assignment, "trip_plan_id", None)
        return {
            "unique_id": assignment.unique_id,
            "trip_date": str(assignment.trip_date),
            "scheduled_time": str(assignment.scheduled_time),
            "status": assignment.status,
            "trip_plan_id": getattr(trip_plan, "unique_id", None),
            "trip_plan_display_code": getattr(trip_plan, "display_code", None),
        }

    def get_customer(self, obj):
        customer = obj.customer_id
        if not customer:
            return None
        name, level = flat_geo_display(customer)
        return {
            "unique_id": customer.unique_id,
            "customer_name": getattr(customer, "customer_name", None),
            "building_no": getattr(customer, "building_no", None),
            "street": getattr(customer, "street", None),
            "location_name": name,
            "location_level": level,
        }

    def get_hierarchy(self, obj):
        name, level = flat_geo_display(obj)
        return {"location_name": name, "location_level": level}
