from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.models.superadmin.user_management.staff_data_scope import StaffDataScope
from app.serializers.superadmin.user_management.staff_access_configuration_serializer import (
    StaffAccessConfigurationSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.hierarchy import filter_staff_queryset_by_requester_scope


class StaffAccessConfigurationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Staffcreation.objects.select_related(
        "personal_details",
        "department_id",
        "designation_id",
        "staffusertype_id",
        "contractorusertype_id",
        "governmentusertype_id",
    ).all()
    serializer_class = StaffAccessConfigurationSerializer
    lookup_field = "staff_unique_id"
    permission_resource = "StaffAccessConfiguration"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["employee_name", "staff_unique_id", "department", "designation"]
    ordering_fields = ["employee_name", "staff_unique_id", "doj"]

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staff-access-configuration"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        staff = result["staff"]
        self.log_audit(
            request,
            instance=staff,
            previous_data=None,
            new_data=self._serialize_instance(staff),
        )
        return Response(
            serializer.to_representation(result),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        previous_data = self._serialize_instance(instance)
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        staff = result["staff"]
        self.log_audit(
            request,
            instance=staff,
            previous_data=previous_data,
            new_data=self._serialize_instance(staff),
        )
        return Response(serializer.to_representation(result))

    @action(detail=False, methods=["get"], url_path="scope-admins")
    def scope_admins(self, request):
        """Admins the caller may place above a new staff account."""
        queryset = Staffcreation.objects.select_related(
            "governmentusertype_id",
        ).filter(
            active_status=True,
            login_enabled=True,
            is_deleted=False,
            governmentusertype_id__name__endswith="_admin",
        )
        if not getattr(request.user, "is_superuser", False):
            scoped_ids = filter_staff_queryset_by_requester_scope(
                queryset,
                request.user,
            ).values_list("staff_unique_id", flat=True)
            requester_id = getattr(request.user, "staff_unique_id", None)
            if not requester_id:
                requester_id = getattr(
                    getattr(request.user, "staff", None),
                    "staff_unique_id",
                    None,
                )
            requester_filter = Q(staff_unique_id=requester_id) if requester_id else Q(pk__in=[])
            queryset = queryset.filter(
                requester_filter | Q(staff_unique_id__in=scoped_ids)
            )

        scopes = {
            scope.staff_id: scope
            for scope in StaffDataScope.objects.filter(
                staff_id__in=queryset.values_list("staff_unique_id", flat=True),
                is_active=True,
                is_deleted=False,
            )
            .select_related("state", "district", "area_type")
            .prefetch_related(
                "corporations",
                "municipalities",
                "town_panchayats",
                "panchayat_unions",
                "panchayats",
                "wards",
            )
        }
        results = []
        body_fields = (
            ("corporation_id", "corporations", "corporation_name", "Corporation"),
            ("municipality_id", "municipalities", "municipality_name", "Municipality"),
            ("town_panchayat_id", "town_panchayats", "town_panchayat_name", "Town Panchayat"),
            ("panchayat_union_id", "panchayat_unions", "union_name", "Panchayat Union"),
            ("panchayat_id", "panchayats", "panchayat_name", "Panchayat"),
        )
        for admin in queryset.order_by("employee_name"):
            scope = scopes.get(admin.staff_unique_id)
            if not scope:
                continue
            hierarchy = []
            if scope.state:
                hierarchy.append({"level": "state", "id": scope.state_id, "name": scope.state.name})
            if scope.district:
                hierarchy.append({"level": "district", "id": scope.district_id, "name": scope.district.name})
            local_bodies = {}
            for key, relation, name_field, label in body_fields:
                entries = [
                    {"id": item.unique_id, "name": getattr(item, name_field), "level": key}
                    for item in getattr(scope, relation).all()
                ]
                local_bodies[key] = entries
                hierarchy.extend(
                    {"level": key, "id": entry["id"], "name": entry["name"], "label": label}
                    for entry in entries
                )
            ward_entries = [
                {"id": ward.unique_id, "name": ward.ward_name}
                for ward in scope.wards.all()
            ]
            hierarchy.extend(
                {"level": "ward", "id": ward["id"], "name": ward["name"], "label": "Ward"}
                for ward in ward_entries
            )
            results.append({
                "id": admin.staff_unique_id,
                "name": admin.employee_name,
                "username": admin.username or "",
                "role": admin.governmentusertype_id.get_name_display(),
                "roleLevel": admin.governmentusertype_id.level,
                "scope": {
                    "stateId": scope.state_id,
                    "districtId": scope.district_id,
                    "areaTypeId": scope.area_type_id,
                    "localBodies": local_bodies,
                    "wards": ward_entries,
                },
                "hierarchy": hierarchy,
            })
        return Response(results)

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            transaction.set_rollback(True)

        return Response(
            {
                "valid": True,
                "summary": {
                    "basicInfo": serializer.validated_data.get("basicInfo", {}),
                    "loginConfig": {
                        key: value
                        for key, value in serializer.validated_data.get("loginConfig", {}).items()
                        if key != "password"
                    },
                    "permissions": len(serializer.validated_data.get("permissions") or []),
                    "dashboardPermissions": len(
                        serializer.validated_data.get("dashboardPermissions") or []
                    ),
                    "dataScope": bool(result.get("data_scope")),
                },
            },
            status=status.HTTP_200_OK,
        )
