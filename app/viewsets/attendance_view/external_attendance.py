from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class ExternalAttendanceViewSet(ViewSet):
    """Server-side proxy for each project's configured attendance provider."""

    permission_classes = [IsAuthenticated]
    swagger_tags = ["Desktop / External Attendance"]

    def _company(self, request):
        user = request.user
        user_company = getattr(user, "company_id", None)
        if user_company is not None:
            return user_company

        if getattr(user, "is_superuser", False):
            company_id = request.query_params.get("company_id")
            if not company_id:
                raise ValidationError({"company_id": "company_id is required"})
            company = Company.objects.filter(
                unique_id=company_id,
                is_deleted=False,
            ).first()
            if company:
                return company
            raise ValidationError({"company_id": "Invalid company_id"})

        raise PermissionDenied("Company user required")

    @staticmethod
    def _project(request, company):
        project_id = request.query_params.get("project_id")
        if not project_id:
            raise ValidationError({"project_id": "project_id is required"})

        project = Project.objects.filter(
            unique_id=project_id,
            company_id=company,
            is_deleted=False,
        ).first()
        if not project:
            raise ValidationError({"project_id": "Invalid project_id for this company"})
        return project

    @staticmethod
    def _date_range(request):
        today = timezone.localdate()
        from_date = parse_date(request.query_params.get("from_date", "")) or today
        to_date = parse_date(request.query_params.get("to_date", "")) or today
        if from_date > to_date:
            raise ValidationError({"to_date": "to_date must be on or after from_date"})
        return from_date, to_date

    def list(self, request):
        company = self._company(request)
        project = self._project(request, company)
        from_date, to_date = self._date_range(request)

        if not project.attendance_api_url or not project.attendance_api_key:
            return Response(
                {"detail": "Attendance API is not configured for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parsed_url = urlsplit(project.attendance_api_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            return Response(
                {"detail": "Configured attendance API URL is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_query = [
            (key, value)
            for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
            if key not in {"from_date", "to_date"}
        ]
        provider_url = urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                urlencode(base_query),
                parsed_url.fragment,
            )
        )

        try:
            upstream = requests.get(
                provider_url,
                params={
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                },
                headers={
                    "X-API-KEY": project.attendance_api_key,
                    "User-Agent": "CronSync/1.0",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            upstream.raise_for_status()
            payload = upstream.json()
        except requests.RequestException as exc:
            return Response(
                {"detail": f"Attendance provider request failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError:
            return Response(
                {"detail": "Attendance provider returned an invalid JSON response."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = payload.get("records", payload.get("data", payload.get("results", [])))
        else:
            records = []

        return Response(
            {
                "company_id": company.unique_id,
                "company_name": company.name,
                "project_id": project.unique_id,
                "project_name": project.name,
                "from_date": from_date,
                "to_date": to_date,
                "count": len(records) if isinstance(records, list) else 0,
                "records": records if isinstance(records, list) else [],
            }
        )
