from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet



class ExternalAttendanceViewSet(ViewSet):
    """Server-side proxy for each project's configured attendance provider."""

    permission_classes = [IsAuthenticated]
    swagger_tags = ["Desktop / External Attendance"]

    @staticmethod
    def _date_range(request):
        today = timezone.localdate()
        from_date = parse_date(request.query_params.get("from_date", "")) or today
        to_date = parse_date(request.query_params.get("to_date", "")) or today
        if from_date > to_date:
            raise ValidationError({"to_date": "to_date must be on or after from_date"})
        return from_date, to_date

    def list(self, request):
        return Response(
            {"detail": "External attendance project configuration was removed with the Project table."},
            status=status.HTTP_410_GONE,
        )
