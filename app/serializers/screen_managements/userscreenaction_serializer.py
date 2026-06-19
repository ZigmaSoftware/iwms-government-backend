from rest_framework import serializers
from app.models.screen_managements.userscreenaction import UserScreenAction


class UserScreenActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserScreenAction
        fields = "__all__"
