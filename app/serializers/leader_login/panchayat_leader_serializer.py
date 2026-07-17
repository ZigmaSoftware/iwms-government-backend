from rest_framework import serializers
from django.contrib.auth.hashers import make_password

from app.models.leader_login.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.panchayat import Panchayat


class PanchayatLeaderLoginSerializer(serializers.ModelSerializer):

    panchayat_id = serializers.PrimaryKeyRelatedField(
        queryset=Panchayat.objects.filter(is_deleted=False),
        required=True,
    )
    panchayat_name = serializers.CharField(
        source="panchayat_id.panchayat_name",
        read_only=True,
    )

    password = serializers.CharField(
        required=False,
        allow_blank=True,
        # write_only=True  ← kept off so edit forms can prefill the hashed value (project pattern)
    )

    class Meta:
        model = PanchayatLeaderLogin
        fields = [
            "unique_id",
            "panchayat_id",
            "panchayat_name",
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

    def validate_panchayat_id(self, value):
        """One panchayat can have at most one (non-deleted) leader."""
        if not value:
            return value
        qs = PanchayatLeaderLogin.objects.filter(
            panchayat_id=value,
            is_deleted=False,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This panchayat already has a leader assigned. "
                "Each panchayat can have only one leader."
            )
        return value

    def validate_username(self, value):
        if not value:
            return value
        qs = PanchayatLeaderLogin.objects.filter(username=value, is_deleted=False)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A panchayat leader with this username already exists.")
        return value

    def create(self, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)
        else:
            raise serializers.ValidationError({"password": "Password is required."})

        return PanchayatLeaderLogin.objects.create(**validated_data)

    def update(self, instance, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
