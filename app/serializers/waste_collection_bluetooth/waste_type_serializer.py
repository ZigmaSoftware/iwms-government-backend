from rest_framework import serializers
from app.models.user_creations.waste_collection_bluetooth import WasteType


class WasteTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteType
        fields = "__all__"
