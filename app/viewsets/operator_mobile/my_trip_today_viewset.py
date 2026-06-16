from rest_framework import status, viewsets
from rest_framework.response import Response

from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.trip_today_serializer import (
    MyTripTodaySerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    find_active_assignment_for_operator,
    resolve_operator_staff,
)


class MyTripTodayViewSet(viewsets.ViewSet):
    """GET /api/v1/operator-mobile/my-trip-today/"""

    permission_classes = [IsOperatorRole]

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
            assignment = find_active_assignment_for_operator(operator)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        data = MyTripTodaySerializer(assignment).data
        return Response(data, status=status.HTTP_200_OK)
