from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.user_creations.waste_collection_bluetooth import WasteCollectionMain


class WasteCollectionMainSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = WasteCollectionMain
        fields = "__all__"
