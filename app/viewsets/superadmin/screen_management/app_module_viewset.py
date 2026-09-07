from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.superadmin.screen_management.app_module import AppModule
from app.serializers.superadmin.screen_management.app_module_serializer import (
    AppModuleSerializer,
)
from app.utils.pagination import LimitOffsetWithPage


class AppModuleViewSet(viewsets.ModelViewSet):
    """Maintain the labels and ordering of the mobile app modules.

    Creating and deleting are refused on purpose. A module only means anything
    if the mobile build has screens and a route for it, so the set of modules
    changes with an app release, not from this screen.
    """

    queryset = AppModule.objects.filter(is_deleted=False)
    serializer_class = AppModuleSerializer
    lookup_field = "unique_id"
    pagination_class = LimitOffsetWithPage
    permission_resource = "AppModule"

    AUDIT_MODULE = "screen-managements"
    AUDIT_ENDPOINT = "app-modules"

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "App modules are defined by the mobile app build and cannot be "
                    "created here. You can rename, reorder or deactivate the "
                    "existing ones."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "App modules cannot be deleted. Deactivate the module instead — "
                    "that stops anyone new being granted it while leaving existing "
                    "grants readable."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_update(self, serializer):
        serializer.save()
        # A deactivated module must stop authorizing logins immediately.
        cache.clear()
