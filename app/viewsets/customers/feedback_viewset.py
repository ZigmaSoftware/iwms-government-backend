from rest_framework import viewsets
from app.models.customers.feedback import FeedBack
from app.serializers.customers.feedback_serializer import FeedBackSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets

class FeedBackViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = FeedBack.objects.filter(is_deleted=False).select_related(
        "customer__ward","customer__zone","customer__city",
        "customer__district","customer__state","customer__country",
        "customer__property_ref","customer__sub_property"
    )
    serializer_class = FeedBackSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "customer-masters"
    AUDIT_ENDPOINT = "feedbacks"
