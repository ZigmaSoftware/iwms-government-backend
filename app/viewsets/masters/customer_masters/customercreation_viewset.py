import re
import csv
import io

from django.db.models import Q, Count
from django.db.models.functions import Upper
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.common_masters.country import Country
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.wastetype import WasteType

from app.serializers.masters.customer_masters.customercreation_serializer import CustomerCreationSerializer

from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets
from app.utils.customer_qr import generate_customer_qr_content, generate_apartment_qr_data


from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.utils.audit_mixin import AuditViewSetMixin

PROPERTY_GROUPING = {
    "apartment": {
        "apartment_name_display": "apartment_name",
        "block_display": "block_no",
    },
    "villa": {
        "villa_number": "villa_no",
    },
    "individual_house": {
        "building_number": "building_no",
    },
}

RESERVED_QUERY_PARAMS = {
    "subproperty", "sub_property", "property", "property_id",
    "sub_property_id", "subproperty_id", "project",
    "format", "search", "ordering", "page", "page_size",
    "limit", "offset",
}


def _normalize_key(value):
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return normalized.strip("_")


def normalize(value):
    return (value or "").strip().upper()



def _build_dynamic_filter_aliases():
    aliases = {}

    for grouping in PROPERTY_GROUPING.values():
        for model_field in grouping.values():
            aliases[model_field] = model_field
            if model_field.endswith("_no"):
                aliases[model_field.replace("_no", "_number")] = model_field

    aliases["block"] = "block_no"
    aliases["apartment_name"] = "apartment_name"
    aliases["flat_no"] = "flat_no"
    aliases["villa_no"] = "villa_no"
    aliases["building_no"] = "building_no"

    return aliases


DYNAMIC_FILTER_ALIASES = _build_dynamic_filter_aliases()




def get_or_create_apartment_qr(apartment_name, request):
    apartment_name = (apartment_name or "").strip().upper()

    obj = CustomerCreation.objects.filter(
        apartment_name__iexact=apartment_name,
        is_deleted=False
    ).first()

    if not obj:
        return None


    # generate QR
    qr_data = generate_apartment_qr_data(obj.apartment_unique_id)
    qr_file = generate_customer_qr_content(qr_data)

    file_name = f"apartment_{apartment_name}.png".replace(" ", "_")

    obj.apartment_qr.save(file_name, qr_file, save=True)

    return obj.apartment_qr.url


class CustomerCreationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    permission_resource = "CustomerCreation"
    serializer_class = CustomerCreationSerializer
    lookup_field = "unique_id"
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    # `register_fcm_token` is a self-service action any authenticated citizen
    # calls for their OWN account (it never touches another customer's row),
    # so it's exempt from the admin module-permission check.
    permission_exempt_actions = ["register_fcm_token"]

    AUDIT_MODULE = "customer-masters"
    AUDIT_ENDPOINT = "customercreations"

    queryset = (
        CustomerCreation.objects
        .filter(is_deleted=False)
        .select_related(
            "state", "district", "area_type",
            "corporation", "municipality", "town_panchayat",
            "panchayat_union", "panchayat",
            "property_ref", "sub_property",
        )
        .prefetch_related("waste_types")
        .order_by("customer_name")
    )


    def get_queryset(self):
        queryset = super().get_queryset()

        params = self.request.query_params
        for field in (
            "state_id", "district_id", "area_type_id",
            "corporation_id", "municipality_id", "town_panchayat_id",
            "panchayat_union_id", "panchayat_id",
        ):
            value = params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})

        waste_type_param = params.get("waste_type_id")
        if waste_type_param:
            waste_type_ids = [v for v in waste_type_param.split(",") if v]
            if waste_type_ids:
                queryset = queryset.filter(waste_types__unique_id__in=waste_type_ids).distinct()

        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)

        return queryset
    

    def perform_create(self, serializer):
        instance = serializer.save()

        if instance.apartment_name:
            get_or_create_apartment_qr(
                instance.apartment_name,
                self.request
            )

        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=new_data
        )


    def perform_update(self, serializer):
        previous_data = self._serialize_instance(serializer.instance)

        instance = serializer.save()

        if instance.apartment_name:
            get_or_create_apartment_qr(
                instance.apartment_name,
                self.request
            )

        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=new_data
        )
    
    # -----------------------------------------------------
    # Subproperty Resolver
    # -----------------------------------------------------

    def _resolve_subproperty_context(self, raw_subproperty):
        cleaned_value = (raw_subproperty or "").strip()
        if not cleaned_value:
            return None, ""

        subproperty = SubProperty.objects.filter(
            is_deleted=False
        ).filter(
            Q(unique_id__iexact=cleaned_value)
            | Q(sub_property_name__iexact=cleaned_value)
        ).first()

        if subproperty:
            return subproperty, _normalize_key(subproperty.sub_property_name)

        normalized = _normalize_key(cleaned_value)

        for row in SubProperty.objects.filter(is_deleted=False).only(
            "unique_id",
            "sub_property_name",
        ):
            if _normalize_key(row.sub_property_name) == normalized:
                return row, normalized

        return None, normalized

    # -----------------------------------------------------
    # FCM device token registration (push notifications)
    # -----------------------------------------------------

    @action(detail=False, methods=["post"], url_path="register-fcm-token")
    def register_fcm_token(self, request):
        """Citizen app calls this after login (and on token refresh) to
        register its Firebase device token, so the backend can push instant
        notifications (e.g. waste collection status updates) to this
        customer. Always acts on the authenticated caller's own record."""
        customer = request.user
        if not isinstance(customer, CustomerCreation):
            return Response(
                {"error": "Only a citizen account can register a device token."},
                status=403,
            )
        token = (request.data.get("fcm_token") or "").strip()
        if not token:
            return Response({"error": "fcm_token is required"}, status=400)
        customer.fcm_token = token
        customer.save(update_fields=["fcm_token"])
        return Response({"status": "ok"})

    # -----------------------------------------------------
    # Apartment Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="apartment-count")
    def apartment_count(self, request):
        queryset = self.filter_queryset(self.get_queryset())


        data = (
            queryset
            .exclude(apartment_name__isnull=True)
            .exclude(apartment_name="")
            .exclude(block_no__isnull=True)
            .exclude(block_no="")
            .exclude(flat_no__isnull=True)
            .exclude(flat_no="")
            .annotate(apartment_name_upper=Upper("apartment_name"))
            .values("apartment_name_upper")
            .annotate(
                user_count=Count("unique_id"),
                block_count=Count("block_no", distinct=True),
                flat_count=Count("unique_id"),
            )
            .order_by("apartment_name_upper")
        )

        response_data = []

        for item in data:
            apartment_name = item["apartment_name_upper"]

            qr_url = get_or_create_apartment_qr(apartment_name, request)

            if qr_url:
                qr_url = request.build_absolute_uri(qr_url)

            response_data.append({
                "apartment_name": apartment_name,
                "user_count": item["user_count"],
                "block_count": item["block_count"],
                "flat_count": item["flat_count"],
                "qr_code": qr_url,
            })

        return Response(response_data)

    # -----------------------------------------------------
    # Block Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="block-count")
    def block_count(self, request):
        apartment_name = request.query_params.get("apartment_name")

        if not apartment_name:
            return Response({"error": "apartment_name is required"}, status=400)

        queryset = self.filter_queryset(self.get_queryset()).filter(
            apartment_name__iexact=apartment_name.strip()
        )

        data = (
            queryset.exclude(block_no__isnull=True)
            .exclude(block_no="")
            .values("block_no")
            .annotate(flat_count=Count("unique_id"))
            .order_by("block_no")
        )

        return Response(list(data))

    # -----------------------------------------------------
    # Flat Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="flat-count")
    def flat_count(self, request):
        apartment_name = request.query_params.get("apartment_name")
        block = request.query_params.get("block")

        if not apartment_name or not block:
            return Response(
                {"error": "apartment_name and block are required"},
                status=400
            )

        queryset = self.filter_queryset(self.get_queryset()).filter(
            apartment_name__iexact=apartment_name.strip(),
            block_no__iexact=block.strip()
        )

        data = (
            queryset.exclude(flat_no__isnull=True)
            .exclude(flat_no="")
            .values("flat_no")
            .annotate(user_count=Count("unique_id"))
            .order_by("flat_no")
        )

        return Response(list(data))

    # -----------------------------------------------------
    # Property User Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="property-user-count")
    def property_user_count(self, request):
        subproperty_value = request.query_params.get("subproperty")

        if not subproperty_value:
            return Response({"error": "subproperty is required"}, status=400)

        subproperty_obj, subproperty_key = self._resolve_subproperty_context(
            subproperty_value
        )

        grouping = PROPERTY_GROUPING.get(subproperty_key)
        if not grouping:
            return Response({"error": "Invalid subproperty"}, status=400)

        queryset = self.filter_queryset(self.get_queryset())

        # ✅ filter by subproperty
        if subproperty_obj:
            queryset = queryset.filter(sub_property=subproperty_obj)

        # ✅ APPLY DYNAMIC FILTERS (MAIN FIX)
        for param, value in request.query_params.items():
            if param in RESERVED_QUERY_PARAMS:
                continue

            model_field = DYNAMIC_FILTER_ALIASES.get(param)

            if model_field and value:
                queryset = queryset.filter(**{
                    f"{model_field}__iexact": value.strip()
                })

        # ✅ remove null/empty values
        for field in grouping.values():
            queryset = queryset.exclude(**{f"{field}__isnull": True}).exclude(
                **{field: ""}
            )

        grouped_data = {}

        for obj in queryset:
            group_key = tuple(
                normalize(getattr(obj, field))
                for field in grouping.values()
            )

            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    **{
                        key: getattr(obj, field)
                        for key, field in grouping.items()
                    },
                    "user_count": 0,
                    "users": []
                }

            user_data = {
                "customer_name": obj.customer_name,
                "contact_no": obj.contact_no,
            }

            if obj.flat_no:
                user_data["flat_no"] = obj.flat_no

            grouped_data[group_key]["users"].append(user_data)
            grouped_data[group_key]["user_count"] += 1

        return Response(list(grouped_data.values()))

    # =========================================================
    # ✅ BULK UPLOAD (NEW - ADDED ONLY)
    # =========================================================

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        def clean(value):
            return (value or "").strip()

        def get_fk(model, field, value):
            value = clean(value)
            if not value:
                return None

            # Try unique_id
            obj = model.objects.filter(unique_id=value).first()
            if obj:
                return obj

            # Try name
            return model.objects.filter(**{f"{field}__iexact": value}).first()

        def get_waste_type_ids(value):
            raw_values = [
                item.strip()
                for item in re.split(r"[,|;]", value or "")
                if item and item.strip()
            ]
            waste_type_ids = []
            invalid_values = []

            for raw_value in raw_values:
                waste_type = (
                    WasteType.objects.filter(unique_id=raw_value, is_deleted=False).first()
                    or WasteType.objects.filter(waste_type_name__iexact=raw_value, is_deleted=False).first()
                )
                if waste_type:
                    waste_type_ids.append(waste_type.unique_id)
                else:
                    invalid_values.append(raw_value)

            return waste_type_ids, invalid_values

        try:
            decoded_file = file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            success_count = 0
            errors = []

            for index, row in enumerate(reader, start=1):

                # ✅ SUPPORT BOTH NAME & ID
                state = get_fk(State, "name", row.get("state_id") or row.get("state_name"))
                country = get_fk(Country, "name", row.get("country_id") or row.get("country_name"))
                property_obj = get_fk(Property, "property_name", row.get("property_id") or row.get("property_name"))
                sub_property = get_fk(SubProperty, "sub_property_name", row.get("sub_property_id") or row.get("sub_property_name"))

                # 🔥 ADD THESE (MISSING IN YOUR CODE)


                district = get_fk(District, "name", row.get("district_id") or row.get("district_name"))
                panchayat = get_fk(Panchayat, "panchayat_name", row.get("panchayat_id") or row.get("panchayat_name"))
                waste_type_ids, invalid_waste_types = get_waste_type_ids(
                    row.get("waste_type_ids") or row.get("waste_types") or row.get("waste_type_names")
                )

                # ✅ VALIDATION
                if not state:
                    errors.append({"row": index, "error": f"Invalid state"})
                    continue

                if not sub_property:
                    errors.append({"row": index, "error": f"Invalid sub_property"})
                    continue

                apartment_name = clean(row.get("apartment_name"))
                block_no = clean(row.get("block_no"))
                flat_no = clean(row.get("flat_no"))

                if "apartment" in (sub_property.sub_property_name or "").lower():
                    if not apartment_name or not block_no:
                        errors.append({
                            "row": index,
                            "error": "Apartment requires apartment_name and block_no"
                        })
                        continue

                if not district:
                    errors.append({
                        "row": index,
                        "error": "District is required"
                    })
                    continue

                if not panchayat:
                    errors.append({
                        "row": index,
                        "error": "Panchayat is required"
                    })
                    continue

                if invalid_waste_types:
                    errors.append({
                        "row": index,
                        "error": f"Invalid waste type(s): {', '.join(invalid_waste_types)}"
                    })
                    continue

                data = {
                    "customer_name": clean(row.get("customer_name")),
                    "contact_no": clean(row.get("contact_no")),

                    "building_no": clean(row.get("building_no")),
                    "street": clean(row.get("street")),
                    "area": clean(row.get("area")),

                    "apartment_name": apartment_name or None,
                    "block_no": block_no or None,
                    "flat_no": flat_no or None,

                    "state_id": state.unique_id,
                    "district_id": district.unique_id,
                    "panchayat_id": panchayat.unique_id,

                    "pincode": clean(row.get("pincode")),
                    "latitude": clean(row.get("latitude")),
                    "longitude": clean(row.get("longitude")),

                    "property_id": property_obj.unique_id if property_obj else None,
                    "sub_property_id": sub_property.unique_id,
                    "waste_type_ids": waste_type_ids,

                    "id_proof_type": clean(row.get("id_proof_type")),
                    "id_no": clean(row.get("id_no")),
                }

                serializer = self.get_serializer(data=data)

                if serializer.is_valid():
                    instance = serializer.save()

                    # 🔥 FIX: QR GENERATED HERE
                    if instance.apartment_name:
                        get_or_create_apartment_qr(
                            instance.apartment_name,
                            request
                        )

                    success_count += 1
                else:
                    errors.append({
                        "row": index,
                        "error": serializer.errors
                    })

            return Response({
                "message": "Bulk upload completed",
                "success_count": success_count,
                "errors": errors
            })

        except Exception as e:
            return Response({"error": str(e)}, status=500)
