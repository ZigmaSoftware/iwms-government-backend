from rest_framework import serializers


def normalize_coordinates(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise serializers.ValidationError("coordinates must be a list.")

    normalized = []
    for index, point in enumerate(value, start=1):
        if isinstance(point, dict):
            latitude = point.get("latitude", point.get("lat"))
            longitude = point.get("longitude", point.get("lng", point.get("lon")))
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            latitude, longitude = point[0], point[1]
        else:
            raise serializers.ValidationError(
                f"coordinates[{index}] must contain latitude and longitude."
            )

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                f"coordinates[{index}] latitude and longitude must be numbers."
            )

        if latitude < -90 or latitude > 90:
            raise serializers.ValidationError(
                f"coordinates[{index}] latitude must be between -90 and 90."
            )
        if longitude < -180 or longitude > 180:
            raise serializers.ValidationError(
                f"coordinates[{index}] longitude must be between -180 and 180."
            )

        normalized.append({"latitude": latitude, "longitude": longitude})

    return normalized


class GeoCoordinateSerializerMixin:
    def validate_coordinates(self, value):
        return normalize_coordinates(value)
