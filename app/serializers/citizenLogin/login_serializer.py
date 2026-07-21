from django.db.models import Q
from rest_framework import serializers

from app.models.superadmin.role_management.userType import UserType


class LoginSerializer(serializers.Serializer):
    # Accept plain strings and validate manually to allow both name and unique_id inputs.
    user_type = serializers.CharField(required=True, help_text="Select the User Type")
    username = serializers.CharField(required=True, help_text="Customer username (contact number or name).")
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        user_type_value = attrs["user_type"].strip()
        username_value = attrs["username"].strip()

        if not user_type_value:
            raise serializers.ValidationError({"user_type": "User type is required."})
        if not username_value:
            raise serializers.ValidationError({"username": "Username is required."})

        user_type_exists = UserType.objects.filter(
            Q(name_iexact=user_type_value) | Q(unique_id_iexact=user_type_value),
            is_active=True,
            is_deleted=False,
        ).exists()

        if not user_type_exists:
            raise serializers.ValidationError({"user_type": "Unknown or inactive user type."})

        attrs["user_type"] = user_type_value
        attrs["username"] = username_value
        return attrs