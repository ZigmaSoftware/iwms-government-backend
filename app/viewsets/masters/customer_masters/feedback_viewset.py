from rest_framework import viewsets
from app.models.masters.customer_masters.feedback import FeedBack
from app.serializers.masters.customer_masters.feedback_serializer import FeedBackSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets

class FeedBackViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "feed_back"
    queryset = FeedBack.objects.filter(is_deleted=False)
    serializer_class = FeedBackSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "customer-masters"
    AUDIT_ENDPOINT = "feedbacks"
