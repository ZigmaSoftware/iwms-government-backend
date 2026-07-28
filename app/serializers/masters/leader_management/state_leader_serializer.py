from rest_framework import serializers
from django.contrib.auth.hashers import make_password

from app.models.masters.leader_management.state_leader_login import StateLeaderLogin
from app.models.superadmin.common_masters.state import State


class StateLeaderLoginSerializer(serializers.ModelSerializer):

    state_id = serializers.PrimaryKeyRelatedField(
        queryset=State.objects.filter(is_deleted=False),
        required=True,
    )
    state_name = serializers.CharField(
        source="state_id.name",
        read_only=True,
    )

    password = serializers.CharField(
        required=False,
        allow_blank=True,
        # write_only=True  ← kept off so edit forms can prefill the hashed value (project pattern)
    )

    class Meta:
        model = StateLeaderLogin
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "username",
            "password",
            "email",
            "leader_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def validate_state_id(self, value):
        """One state can have at most one (non-deleted) leader."""
        if not value:
            return value
        qs = StateLeaderLogin.objects.filter(
            state_id=value,
            is_deleted=False,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This state already has a leader assigned. "
                "Each state can have only one leader."
            )
        return value

    def validate_username(self, value):
        if not value:
            return value
        qs = StateLeaderLogin.objects.filter(username=value, is_deleted=False)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A state leader with this username already exists.")
        return value

    def create(self, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)
        else:
            raise serializers.ValidationError({"password": "Password is required."})

        return StateLeaderLogin.objects.create(**validated_data)

    def update(self, instance, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
