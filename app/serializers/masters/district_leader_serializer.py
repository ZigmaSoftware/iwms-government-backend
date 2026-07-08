from rest_framework import serializers
from django.contrib.auth.hashers import make_password

from app.models.masters.district_leader_login import DistrictLeaderLogin
from app.models.masters.district import District


class DistrictLeaderLoginSerializer(serializers.ModelSerializer):

    district_id = serializers.PrimaryKeyRelatedField(
        queryset=District.objects.filter(is_deleted=False),
        required=True,
    )
    district_name = serializers.CharField(
        source="district_id.name",
        read_only=True,
    )

    password = serializers.CharField(
        required=False,
        allow_blank=True,
        # write_only=True  ← kept off so edit forms can prefill the hashed value (project pattern)
    )

    class Meta:
        model = DistrictLeaderLogin
        fields = [
            "unique_id",
            "district_id",
            "district_name",
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

    def validate_district_id(self, value):
        """One district can have at most one (non-deleted) leader."""
        if not value:
            return value
        qs = DistrictLeaderLogin.objects.filter(
            district_id=value,
            is_deleted=False,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This district already has a leader assigned. "
                "Each district can have only one leader."
            )
        return value

    def validate_username(self, value):
        if not value:
            return value
        qs = DistrictLeaderLogin.objects.filter(username=value, is_deleted=False)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A district leader with this username already exists.")
        return value

    def create(self, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)
        else:
            raise serializers.ValidationError({"password": "Password is required."})

        return DistrictLeaderLogin.objects.create(**validated_data)

    def update(self, instance, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
