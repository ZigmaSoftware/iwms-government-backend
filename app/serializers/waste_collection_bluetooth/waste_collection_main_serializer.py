from rest_framework import serializers
from app.models.user_creations.waste_collection_bluetooth import WasteCollectionMain


class WasteCollectionMainSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteCollectionMain
        fields = "__all__"
