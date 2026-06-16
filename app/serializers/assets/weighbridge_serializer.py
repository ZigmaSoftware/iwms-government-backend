from rest_framework import serializers
from app.models.assets.weighbridge import WeighbridgeCheck
from app.models.schedule_masters.trip_plan import TripPlan
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class WeighbridgeCheckSerializer(TenancyReadSerializerMixin,serializers.ModelSerializer):

    trip_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=TripPlan.objects.all()
    )

    vehicle_no = serializers.CharField(source = "trip_id.vehicle_id.vehicle_no", read_only = True)
    wastetype = serializers.CharField(source = "trip_id.waste_type_id.waste_type_name", read_only = True)


    class Meta:
        model = WeighbridgeCheck
        fields = [
            "unique_id",
            "trip_id",
            "vehicle_no",
            "wastetype",
            "total_collected_weight",
            "weighbridge_weight",
            "weight_difference",
            "status",
            "checked_date",
            "collected_date",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id", "weight_difference", "status"]
