# =========================================================
# serializers/screen_managements/userscreen_serializer.py
# =========================================================

from django.db import transaction

from rest_framework import serializers

from app.serializers.company_projects.tenancy import (
    TenancyReadSerializerMixin
)

from app.models.screen_managements.userscreen import UserScreen

from app.utils.userscreen_column_sync import (
    sync_screen_columns
)
from app.utils.model_mapper import resolve_userscreen_model


class UserScreenSerializer(
    
    serializers.ModelSerializer
):

    # =====================================================
    # READ ONLY FIELDS
    # =====================================================

    mainscreen_name = serializers.CharField(
        source="mainscreen_id.mainscreen_name",
        read_only=True
    )

    mainscreentype_id = serializers.CharField(
        source="mainscreen_id.mainscreentype_id.unique_id",
        read_only=True
    )

    mainscreentype_name = serializers.CharField(
        source="mainscreen_id.mainscreentype_id.type_name",
        read_only=True
    )

    # =====================================================
    # OPTIONAL FIELDS
    # =====================================================

    order_no = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    icon_name = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:

        model = UserScreen

        fields = "__all__"

        extra_kwargs = {

            "order_no": {
                "required": False,
                "allow_null": True
            },

            "icon_name": {
                "required": False,
                "allow_blank": True,
                "allow_null": True
            },

            # =============================================
            # OPTIONAL — ONLY NEEDED FOR AUTO SYNC
            # =============================================

            "model_app_label": {
                "required": False,
                "allow_null": True,
                "allow_blank": True,
            },

            "model_name": {
                "required": False,
                "allow_null": True,
                "allow_blank": True,
            },
        }

    # =====================================================
    # AUTO ORDER NUMBER
    # =====================================================

    def _next_order_no(self, mainscreen_id):

        with transaction.atomic():

            last = (
                UserScreen.objects
                .select_for_update()
                .filter(
                    mainscreen_id=mainscreen_id,
                    is_deleted=False
                )
                .order_by("-order_no")
                .first()
            )

            return (last.order_no if last else 0) + 1

    # =====================================================
    # VALIDATION
    # =====================================================

    def validate(self, data):

        mainscreen = (
            data.get("mainscreen_id")
            or getattr(self.instance, "mainscreen_id", None)
        )

        order_no = data.get("order_no")

        # =================================================
        # UNIQUE ORDER VALIDATION
        # =================================================

        if order_no is not None and mainscreen:

            queryset = UserScreen.objects.filter(
                mainscreen_id=mainscreen,
                order_no=order_no,
                is_deleted=False
            )

            if self.instance:

                queryset = queryset.exclude(
                    unique_id=self.instance.unique_id
                )

            if queryset.exists():

                raise serializers.ValidationError({
                    "order_no":
                        "This order number already exists for this Main Screen."
                })

        # =================================================
        # MODEL VALIDATION
        # =================================================

        model_app_label = (
            data.get("model_app_label")
            or getattr(self.instance, "model_app_label", None)
        )

        model_name = (
            data.get("model_name")
            or getattr(self.instance, "model_name", None)
        )

        # =================================================
        # BOTH REQUIRED TOGETHER
        # =================================================

        if bool(model_app_label) != bool(model_name):

            raise serializers.ValidationError({
                "model_name":
                    "Both model_app_label and model_name are required together."
            })

        return data

    # =====================================================
    # CREATE
    # =====================================================

    def create(self, validated_data):

        # =================================================
        # AUTO ICON
        # =================================================

        if not validated_data.get("icon_name"):

            validated_data["icon_name"] = (
                validated_data.get("userscreen_name") or ""
            ).strip()

        # =================================================
        # AUTO ORDER NUMBER
        # =================================================

        if validated_data.get("order_no") in (None, ""):

            validated_data["order_no"] = self._next_order_no(
                validated_data.get("mainscreen_id")
            )

        # =================================================
        # CREATE SCREEN
        # =================================================

        instance = super().create(validated_data)

        if resolve_userscreen_model(instance):
            sync_screen_columns(instance)

        return instance

    # =====================================================
    # UPDATE
    # =====================================================

    def update(self, instance, validated_data):

        # =================================================
        # ORDER NO OPTIONAL
        # =================================================

        if (
            "order_no" not in validated_data
            or validated_data.get("order_no") is None
        ):
            validated_data.pop("order_no", None)

        # =================================================
        # ICON OPTIONAL
        # =================================================

        if (
            "icon_name" not in validated_data
            or validated_data.get("icon_name") in (None, "")
        ):
            validated_data.pop("icon_name", None)

        # =================================================
        # UPDATE SCREEN
        # =================================================

        instance = super().update(instance, validated_data)

        # =================================================
        # RE-SYNC COLUMNS
        # =================================================

        if resolve_userscreen_model(instance):
            sync_screen_columns(instance)

        return instance
