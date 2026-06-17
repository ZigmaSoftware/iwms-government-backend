from rest_framework import serializers
from app.models.grivences.complaints import Complaint


class ComplaintSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    customer_id = serializers.CharField(source="customer.unique_id", read_only=True)
    zone_id = serializers.CharField(source="zone.unique_id", read_only=True)
    ward_id = serializers.CharField(source="ward.unique_id", read_only=True)
    zone_name = serializers.CharField(source="zone.zone_name", read_only=True)
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True)
    main_category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sub_category = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    image_url = serializers.SerializerMethodField()
    close_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = "__all__"
        extra_kwargs = {
            "customer": {"write_only": True},
            "zone": {"write_only": True, "required": False, "allow_null": True},
            "ward": {"write_only": True, "required": False, "allow_null": True},
        }

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_close_image_url(self, obj):
        request = self.context.get("request")
        if obj.close_image:
            return request.build_absolute_uri(obj.close_image.url)
        return None
