from rest_framework import status, viewsets
from rest_framework.response import Response

from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.scan_serializers import (
    ValidateBinQrRequestSerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    build_scan_context,
    progress_payload,
    resolve_operator_staff,
    serialize_assignment_brief,
    serialize_bin_brief,
    serialize_cp_brief,
    serialize_trip_cp_brief,
)


class ValidateBinQrViewSet(viewsets.ViewSet):
    """POST /api/v1/operator-mobile/validate-bin-qr/"""

    permission_classes = [IsOperatorRole]

    def create(self, request):
        serializer = ValidateBinQrRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            operator = resolve_operator_staff(request.user)
            ctx = build_scan_context(
                serializer.validated_data["bin_qr"], operator
            )
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        return Response(
            {
                "bin": serialize_bin_brief(ctx.bin, request=request),
                "collection_point": serialize_cp_brief(ctx.bin.collection_point_id),
                "trip_collection_point": serialize_trip_cp_brief(ctx.trip_cp),
                "assignment": serialize_assignment_brief(ctx.assignment),
                "trip_progress": progress_payload(ctx.assignment),
            },
            status=status.HTTP_200_OK,
        )
