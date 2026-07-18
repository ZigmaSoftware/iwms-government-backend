import os

from django.conf import settings
from rest_framework import serializers

from app.models.attendance import DailyAttendanceReg


class DailyAttendanceRegSerializer(serializers.ModelSerializer):
    captured_image = serializers.SerializerMethodField()

    class Meta:
        model = DailyAttendanceReg
        fields = [
            "unique_id",
            "staff_id",
            "emp_id",
            "name",
            "recognition_date",
            "recognition_time",
            "punch_type",
            "similarity_score",
            "latitude",
            "longitude",
            "captured_image",
        ]

    def get_captured_image(self, obj):
        if not obj.captured_image_path or isinstance(
            obj.captured_image_path, (bytes, bytearray, memoryview)
        ):
            return None

        filename = os.path.basename(str(obj.captured_image_path))
        media_url = f"{settings.MEDIA_URL}captured_images/{filename}"
        request = self.context.get("request")
        return request.build_absolute_uri(media_url) if request else media_url
