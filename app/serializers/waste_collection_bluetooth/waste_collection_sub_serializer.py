from rest_framework import serializers
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteCollectionSub


class WasteCollectionSubSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteCollectionSub
        fields = "__all__"
        read_only_fields = ["date_time"]
