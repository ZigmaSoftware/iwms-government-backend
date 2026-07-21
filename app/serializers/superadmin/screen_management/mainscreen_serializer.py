from django.db import transaction
from rest_framework import serializers
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.validators.superadmin.screen_management.order_no_validators import validate_unique_order_no

class MainScreenSerializer(serializers.ModelSerializer):
    mainscreentype_name = serializers.CharField(
        source="mainscreentype_id.type_name",
        read_only=True
    )
    # Backend is source of truth for ordering; allow clients to omit this.
    order_no = serializers.IntegerField(required=False, allow_null=True)
    # UI no longer sends icon_name; derive it from mainscreen_name if omitted.
    icon_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = MainScreen
        fields = "__all__"
        extra_kwargs = {
            "order_no": {"required": False, "allow_null": True},
            "icon_name": {"required": False, "allow_blank": True, "allow_null": True},
        }

    def _next_order_no(self, mainscreentype_id):
        with transaction.atomic():
            last = (
                MainScreen.objects.select_for_update()
                .filter(mainscreentype_id=mainscreentype_id, is_deleted=False)
                .order_by("-order_no")
                .first()
            )
            return (last.order_no if last else 0) + 1

    def create(self, validated_data):
        if not validated_data.get("icon_name"):
            validated_data["icon_name"] = (validated_data.get("mainscreen_name") or "").strip()
        # If not provided, auto-generate next order_no within this MainScreenType.
        if validated_data.get("order_no") in (None, ""):
            validated_data["order_no"] = self._next_order_no(validated_data.get("mainscreentype_id"))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # If client omits order_no, keep existing order_no.
        if "order_no" not in validated_data or validated_data.get("order_no") is None:
            validated_data.pop("order_no", None)
        # If client omits icon_name, keep existing icon_name.
        if "icon_name" not in validated_data or validated_data.get("icon_name") in (None, ""):
            validated_data.pop("icon_name", None)
        return super().update(instance, validated_data)

    def validate(self, data):
        mainscreentype = data.get("mainscreentype_id") or getattr(self.instance, "mainscreentype_id", None)
        order_no = data.get("order_no")

        validate_unique_order_no(
            MainScreen,
            "mainscreentype_id",
            mainscreentype,
            order_no,
            self.instance,
            "This order number already exists for this Main Screen Type.",
        )

        return data
