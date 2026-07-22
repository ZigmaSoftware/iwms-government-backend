from rest_framework import filters, status
from rest_framework.response import Response

from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets
from app.models.masters.leader_management.state_leader_login import StateLeaderLogin
from app.serializers.masters.leader_management.state_leader_serializer import StateLeaderLoginSerializer


class StateLeaderLoginViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = StateLeaderLogin.objects.select_related(
        "state_id",
    ).filter(is_deleted=False)

    serializer_class = StateLeaderLoginSerializer
    lookup_field = "unique_id"
    permission_resource = "StateLeaderLogin"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "state-leaders"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "leader_name", "email", "state_id__name"]
    ordering_fields = ["username", "created_at"]

    def get_queryset(self):
        qs = StateLeaderLogin.objects.select_related(
            "state_id"
        ).filter(is_deleted=False)

        state_id = self.request.query_params.get("state_id")
        if state_id:
            qs = qs.filter(state_id__unique_id=state_id)

        return qs.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            new_data = self._serialize_instance(instance)
            self.log_audit(request, instance=instance, previous_data=None, new_data=new_data)
            return Response(
                {"status": True, "message": "State Leader created successfully."},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop("partial", False)
        )
        if serializer.is_valid():
            previous_data = self._serialize_instance(instance)
            updated = serializer.save()
            new_data = self._serialize_instance(updated)
            self.log_audit(request, instance=updated, previous_data=previous_data, new_data=new_data)
            return Response(
                {"status": True, "message": "State Leader updated successfully."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        previous_data = self._serialize_instance(instance)
        self.log_audit(request, instance=instance, previous_data=previous_data, new_data=None)
        instance.delete()
        return Response(
            {"status": True, "message": "State Leader deleted successfully."},
            status=status.HTTP_200_OK,
        )
