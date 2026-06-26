from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.masters.hierarchy_tree import HierarchyLevel, HierarchyNode
from app.serializers.masters.hierarchy_tree_serializer import (
    HierarchyLevelSerializer,
    HierarchyNodeSerializer,
)
from app.services import hierarchy_tree_service as svc
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class HierarchyLevelViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """CRUD for hierarchy level templates (Country, State, Ward, ...)."""

    queryset = HierarchyLevel.objects.filter(is_deleted=False)
    serializer_class = HierarchyLevelSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "code"]
    ordering_fields = ["order", "name", "is_active"]
    permission_resource = "HierarchyLevel"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "hierarchy-levels"

    def perform_destroy(self, instance):
        instance.delete()  # soft delete


class HierarchyNodeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for hierarchy nodes plus closure-table read actions.

    Create / update / move / delete are routed through the closure service so
    the ``hierarchy_tree_closure`` table is always kept consistent. The standard
    audit log (CommonAudit) is still written via the mixin's ``log_audit``.
    """

    queryset = HierarchyNode.objects.filter(is_deleted=False)
    serializer_class = HierarchyNodeSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "code", "level__name"]
    ordering_fields = ["name", "level__order", "is_active"]
    permission_resource = "HierarchyNode"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "hierarchy-nodes"

    @classmethod
    def get_extra_actions(cls):
        """
        Restore DRF's real ``@action`` discovery for this viewset.

        ``AuditViewSetMixin`` overrides ``get_extra_actions`` and (in this
        codebase) ends up returning an empty list, which would drop our
        tree / path / descendants / context routes. We bypass the mixin and
        call DRF's ``ViewSetMixin`` implementation directly so the custom
        actions are registered correctly. Scoped to this viewset only.
        """
        return viewsets.ViewSetMixin.get_extra_actions.__func__(cls)

    def get_queryset(self):
        queryset = HierarchyNode.objects.filter(is_deleted=False).select_related(
            "level", "parent"
        )
        parent_id = self.request.query_params.get("parent") or self.request.query_params.get("parent_id")
        level_id = self.request.query_params.get("level") or self.request.query_params.get("level_id")
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        if level_id:
            queryset = queryset.filter(level_id=level_id)
        return queryset

    # -- write ops routed through the closure service -----------------------

    def create(self, request, *args, **kwargs):
        data = request.data
        try:
            node = svc.create_node(
                level_id=data.get("level") or data.get("level_id"),
                parent_id=data.get("parent") or data.get("parent_id") or None,
                name=data.get("name"),
                code=data.get("code", ""),
                custom_properties=data.get("custom_properties"),
            )
        except (DjangoValidationError, HierarchyLevel.DoesNotExist, HierarchyNode.DoesNotExist) as exc:
            return Response({"detail": _msg(exc)}, status=status.HTTP_400_BAD_REQUEST)

        self._safe_audit(request, instance=node, previous_data=None,
                         new_data=self._serialize_instance(node))
        return Response(self.get_serializer(node).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        node_id = kwargs.get(self.lookup_field)
        data = request.data
        try:
            existing = HierarchyNode.objects.get(unique_id=node_id, is_deleted=False)
            previous_data = self._serialize_instance(existing)
            node = svc.update_node(
                node_id,
                level_id=(data.get("level") or data.get("level_id")) if ("level" in data or "level_id" in data) else None,
                parent_id=(data.get("parent") or data.get("parent_id") or None) if ("parent" in data or "parent_id" in data) else None,
                name=data.get("name") if "name" in data else None,
                code=data.get("code") if "code" in data else None,
                is_active=data.get("is_active") if "is_active" in data else None,
                custom_properties=data.get("custom_properties") if "custom_properties" in data else None,
            )
        except HierarchyNode.DoesNotExist as exc:
            return Response({"detail": _msg(exc)}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, HierarchyLevel.DoesNotExist) as exc:
            return Response({"detail": _msg(exc)}, status=status.HTTP_400_BAD_REQUEST)

        self._safe_audit(request, instance=node, previous_data=previous_data,
                         new_data=self._serialize_instance(node))
        return Response(self.get_serializer(node).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        node_id = kwargs.get(self.lookup_field)
        try:
            instance = HierarchyNode.objects.get(unique_id=node_id, is_deleted=False)
            previous_data = self._serialize_instance(instance)
            svc.delete_subtree(node_id)
        except HierarchyNode.DoesNotExist as exc:
            return Response({"detail": _msg(exc)}, status=status.HTTP_404_NOT_FOUND)

        self._safe_audit(request, instance=instance, previous_data=previous_data, new_data=None)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- closure read actions ----------------------------------------------

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        return Response(svc.build_tree())

    @action(detail=True, methods=["get"], url_path="path")
    def path(self, request, unique_id=None):
        return Response(svc.get_path(unique_id))

    @action(detail=True, methods=["get"], url_path="descendants")
    def descendants(self, request, unique_id=None):
        return Response(svc.get_descendants(unique_id))

    @action(detail=True, methods=["get"], url_path="context")
    def context(self, request, unique_id=None):
        return Response(svc.get_context(unique_id))

    # -- helpers ------------------------------------------------------------

    def _safe_audit(self, request, *, instance, previous_data, new_data):
        """Write the CommonAudit row; never let an audit failure break the op."""
        try:
            self.log_audit(
                request,
                instance=instance,
                previous_data=previous_data,
                new_data=new_data,
            )
        except Exception:
            pass


def _msg(exc):
    if hasattr(exc, "messages") and exc.messages:
        return "; ".join(exc.messages)
    return str(exc)
