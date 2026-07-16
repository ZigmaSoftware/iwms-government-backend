from rest_framework import status, viewsets
from rest_framework.response import Response

from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.trip_today_serializer import (
    MyTripTodaySerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    find_active_assignment_for_operator,
    find_all_active_assignments_for_operator,
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

        data = MyTripTodaySerializer(assignment, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)


class MyTripsTodayViewSet(viewsets.ViewSet):
    """GET /api/v1/operator-mobile/my-trips-today/

    ALL of the operator's trips today (a driver may hold e.g. a bin trip AND a
    household trip). Returns `{"results": [...]}` so the app can show a header
    carousel. Empty list (not an error) when there is no trip today."""

    permission_classes = [IsOperatorRole]

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )
        assignments = find_all_active_assignments_for_operator(operator)
        data = MyTripTodaySerializer(
            assignments, many=True, context={"request": request}
        ).data
        return Response({"results": data}, status=status.HTTP_200_OK)
