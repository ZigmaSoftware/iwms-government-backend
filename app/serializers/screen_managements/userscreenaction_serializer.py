from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.screen_managements.userscreenaction import UserScreenAction


class UserScreenActionSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = UserScreenAction
        fields = "__all__"
