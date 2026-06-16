from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.user_creations.attendance import Recognized
from django.conf import settings
import os


class AttendanceListSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    captured_image = serializers.SerializerMethodField()

    class Meta:
        model = Recognized
        fields = [
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "id",
            "emp_id",
            "name",
            "recognition_date",
            "recognition_time",
            "latitude",
            "longitude",
            "captured_image",
        ]

    def get_captured_image(self, obj):
        if not obj.captured_image_path:
            return None

        if isinstance(obj.captured_image_path, (bytes, bytearray, memoryview)):
            return None

        path = str(obj.captured_image_path)
        filename = os.path.basename(path)
        return f"{settings.MEDIA_URL}captured_images/{filename}"
