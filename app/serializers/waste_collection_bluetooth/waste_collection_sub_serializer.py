from rest_framework import serializers
from app.models.user_creations.waste_collection_bluetooth import WasteCollectionSub


class WasteCollectionSubSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteCollectionSub
        fields = "__all__"
        read_only_fields = ["date_time"]
