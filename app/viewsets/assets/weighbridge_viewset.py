from django.db.models import Sum
from rest_framework.response import Response
from datetime import date
from app.serializers.assets.weighbridge_serializer import WeighbridgeCheckSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class WeighbridgeCheckViewSet(AuditViewSetMixin, viewsets.ModelViewSet):

    serializer_class = WeighbridgeCheckSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="weighbridge"

    def get_queryset(self):
        return WeighbridgeCheck.objects.select_related(
            "trip_id",
            "trip_id__vehicle_id",
            "trip_id__waste_type_id"
        ).filter(is_deleted=False)

    def list(self, request, *args, **kwargs):

        queryset = self.get_queryset()

        # 🔎 FILTERS
        trip_id = request.query_params.get("trip_id")
        if trip_id:
            queryset = queryset.filter(trip_id=trip_id)

        checked_date = request.query_params.get("checked_date")
        if checked_date:
            queryset = queryset.filter(checked_date=checked_date)

        collected_date = request.query_params.get("collected_date")
        if collected_date:
            queryset = queryset.filter(collected_date=collected_date)

        status = request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        serializer = self.get_serializer(queryset, many=True)

        # 📊 AGGREGATIONS
        today = date.today()

        daily_total = queryset.filter(
            checked_date=today
        ).aggregate(total=Sum("weighbridge_weight"))

        overall_total = queryset.aggregate(
            total=Sum("weighbridge_weight")
        )

        total_difference = queryset.aggregate(
            total=Sum("weight_difference")
        )

        return Response({
            "date": today,
            "daily_total_weighbridge_weight": daily_total["total"] or 0,
            "overall_total_weighbridge_weight": overall_total["total"] or 0,
            "overall_weight_difference": total_difference["total"] or 0,
            "results": serializer.data
        })


