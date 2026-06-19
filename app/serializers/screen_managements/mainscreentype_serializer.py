from rest_framework import serializers
from app.models.screen_managements.mainscreentype import MainScreenType


class MainScreenTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MainScreenType
        fields = "__all__"
