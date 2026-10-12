from rest_framework import filters, status
from rest_framework.response import Response
from rest_framework.decorators import action

import csv
import io

from app.utils.file_archive import archive_bytes

from app.utils.list_filters import ListParamFilter
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from rest_framework import viewsets
from app.models.masters.leader_management.state_leader_login import StateLeaderLogin
from app.serializers.masters.leader_management.state_leader_serializer import StateLeaderLoginSerializer


class StateLeaderLoginViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "state_leader_login"
    # state_id is now a plain unique_id CharField (no DB relation), so it
    # can no longer be select_related.
    queryset = StateLeaderLogin.objects.filter(is_deleted=False)

    serializer_class = StateLeaderLoginSerializer
    lookup_field = "unique_id"
    permission_resource = "StateLeaderLogin"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "state-leaders"

    filter_backends = [ListParamFilter, filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["username", "leader_name", "email"]
    ordering_fields = ["username", "created_at"]

    def get_queryset(self):
        qs = StateLeaderLogin.objects.filter(is_deleted=False)

        state_id = self.request.query_params.get("state_id")
        if state_id:
            qs = qs.filter(state_id=state_id)

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

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "CSV file is required"}, status=400)
        try:
            _upload_content = file.read()
            decoded = _upload_content.decode("utf-8")
            try:
                _archived = archive_bytes(
                    _upload_content,
                    getattr(file, "name", None) or "state_leader_bulk_upload.csv",
                    subdir="bulk_uploads/state_leaders",
                )
            except Exception:
                _archived = {"archived": False}
        except Exception as exc:
            return Response({"error": "Unable to decode CSV file", "detail": str(exc)}, status=400)

        reader = csv.DictReader(io.StringIO(decoded))
        success_count = 0
        errors: list[dict] = []
        for index, row in enumerate(reader, start=1):
            payload = {
                "username": (row.get("username") or "").strip() or None,
                "password": (row.get("password") or "").strip() or None,
                "leader_name": (row.get("leader_name") or "").strip() or None,
                "email": (row.get("email") or "").strip() or None,
                "state_id": (row.get("state_id") or row.get("state_name") or "").strip() or None,
            }
            is_active_value = (row.get("is_active") or "").strip().lower()
            if is_active_value:
                payload["is_active"] = is_active_value in {"true", "1", "yes", "y"}
            serializer = self.get_serializer(data=payload)
            if serializer.is_valid():
                serializer.save()
                success_count += 1
            else:
                errors.append({"row": index, "error": serializer.errors, "data": row})
        return Response({
            "message": "State leader bulk upload completed",
            "success_count": success_count,
            "error_count": len(errors),
            "total_count": success_count + len(errors),
            "errors": errors,
            "file_name": getattr(file, "name", None),
            "file_url": _archived.get("file_url") if _archived.get("archived") else None,
        })
