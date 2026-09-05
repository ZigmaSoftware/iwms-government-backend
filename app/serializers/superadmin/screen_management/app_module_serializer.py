from rest_framework import serializers

from app.models.superadmin.screen_management.app_module import AppModule


class AppModuleSerializer(serializers.ModelSerializer):
    """The mobile app module master.

    `module_key`, `surface_key` and `route` are read-only: each module is
    backed by screens and routes that ship inside the Flutter build, so one
    invented in web would appear in every dropdown and route nowhere. The
    label, ordering and active flag are yours to maintain.
    """

    screen_count = serializers.SerializerMethodField()

    class Meta:
        model = AppModule
        fields = [
            "unique_id",
            "module_key",
            "surface_key",
            "label",
            "route",
            "order_no",
            "description",
            "is_active",
            "screen_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "module_key",
            "surface_key",
            "route",
            "created_at",
            "updated_at",
        ]

    def get_screen_count(self, obj):
        from app.utils.app_feature_grants import SCREEN_PERMISSIONS

        prefix = f"{obj.surface_key}."
        return sum(1 for key in SCREEN_PERMISSIONS if key.startswith(prefix))
