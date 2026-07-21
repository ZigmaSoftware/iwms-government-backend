from rest_framework import serializers
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction


class UserScreenActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserScreenAction
        fields = "__all__"
