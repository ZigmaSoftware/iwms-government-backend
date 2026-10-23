from rest_framework import serializers


class EvidenceImageField(serializers.ImageField):
    """Strict image field shared by mobile operational-evidence endpoints."""

    max_size = 10 * 1024 * 1024
    allowed_content_types = {"image/jpeg", "image/png", "image/webp"}

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if value.size > self.max_size:
            raise serializers.ValidationError("Evidence image must be 10 MB or smaller.")
        content_type = (getattr(value, "content_type", "") or "").lower()
        if content_type not in self.allowed_content_types:
            raise serializers.ValidationError("Use a JPEG, PNG, or WebP evidence image.")
        return value


def absolute_image_url(serializer, image_field):
    if not image_field:
        return None
    try:
        url = image_field.url
    except (ValueError, AttributeError):
        return None
    request = serializer.context.get("request")
    return request.build_absolute_uri(url) if request else url
