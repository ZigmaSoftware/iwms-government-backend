from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.masters.hierarchy_assignment import HierarchyAssignment
from app.serializers.masters.hierarchy_assignment_serializer import (
    HierarchyAssignmentSerializer,
)
from app.services import hierarchy_assignment_service as svc
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.hierarchy_entities import list_entity_records, list_entity_types


class HierarchyAssignmentViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """
    Generic "attach any master to any hierarchy node" API.

    Standard CRUD plus helper actions that the frontend "Assign Hierarchy" form
    consumes to build its dropdowns and show current assignments.
    """

    queryset = HierarchyAssignment.objects.filter(is_deleted=False)
    serializer_class = HierarchyAssignmentSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["entity_type", "entity_label", "node__name"]
    ordering_fields = ["entity_type", "is_primary"]
    permission_resource = "HierarchyAssignment"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "hierarchy-assignments"

    @classmethod
    def get_extra_actions(cls):
        # AuditViewSetMixin shadows DRF's action discovery; restore it here.
        return viewsets.ViewSetMixin.get_extra_actions.__func__(cls)

    def get_queryset(self):
        qs = HierarchyAssignment.objects.filter(is_deleted=False).select_related(
            "node", "node__level"
        )
        entity_type = self.request.query_params.get("entity_type")
        entity_id = self.request.query_params.get("entity_id")
        node = self.request.query_params.get("node")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        if node:
            qs = qs.filter(node_id=node)
        return qs

    # -- write ops routed through the service -------------------------------

    def create(self, request, *args, **kwargs):
        data = request.data
        try:
            assignment = svc.assign(
                node_id=data.get("node") or data.get("node_id"),
                entity_type=data.get("entity_type"),
                entity_id=data.get("entity_id"),
                is_primary=data.get("is_primary", True),
            )
        except DjangoValidationError as exc:
            return Response({"detail": _msg(exc)}, status=status.HTTP_400_BAD_REQUEST)
        self._safe_audit(request, instance=assignment, previous_data=None,
                         new_data=self._serialize_instance(assignment))
        return Response(self.get_serializer(assignment).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        assignment_id = kwargs.get(self.lookup_field)
        try:
            instance = HierarchyAssignment.objects.get(
                unique_id=assignment_id, is_deleted=False
            )
            previous_data = self._serialize_instance(instance)
            svc.unassign(assignment_id)
        except (HierarchyAssignment.DoesNotExist, DjangoValidationError) as exc:
            return Response({"detail": _msg(exc)}, status=status.HTTP_404_NOT_FOUND)
        self._safe_audit(request, instance=instance, previous_data=previous_data, new_data=None)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- form helper actions ------------------------------------------------

    @action(detail=False, methods=["get"], url_path="entity-types")
    def entity_types(self, request):
        """List of assignable master types: [{key, label}]."""
        return Response(list_entity_types())

    @action(detail=False, methods=["get"], url_path="entity-records")
    def entity_records(self, request):
        """Selectable records for one master type: ?entity_type=department."""
        entity_type = request.query_params.get("entity_type")
        if not entity_type:
            return Response({"detail": "entity_type is required"}, status=400)
        return Response(list_entity_records(entity_type))

    @action(detail=False, methods=["get"], url_path="for-entity")
    def for_entity(self, request):
        """Assignments (with ancestry path) for ?entity_type=&entity_id=."""
        entity_type = request.query_params.get("entity_type")
        entity_id = request.query_params.get("entity_id")
        if not entity_type or not entity_id:
            return Response({"detail": "entity_type and entity_id are required"}, status=400)
        return Response(svc.for_entity(entity_type, entity_id))

    @action(detail=False, methods=["get"], url_path="under-node")
    def under_node(self, request):
        """
        Entities under a node (?node=). Rolls up through the closure table by
        default; pass ?descendants=false to restrict to the exact node.
        """
        node_id = request.query_params.get("node") or request.query_params.get("node_id")
        if not node_id:
            return Response({"detail": "node is required"}, status=400)
        entity_type = request.query_params.get("entity_type")
        include_desc = request.query_params.get("descendants", "true").lower() != "false"
        return Response(
            svc.under_node(node_id, entity_type=entity_type, include_descendants=include_desc)
        )

    # -- helpers ------------------------------------------------------------

    def _safe_audit(self, request, *, instance, previous_data, new_data):
        try:
            self.log_audit(request, instance=instance,
                           previous_data=previous_data, new_data=new_data)
        except Exception:
            pass


def _msg(exc):
    if hasattr(exc, "messages") and exc.messages:
        return "; ".join(exc.messages)
    return str(exc)
