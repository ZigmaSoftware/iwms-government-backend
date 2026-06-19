from rest_framework import viewsets, status
from rest_framework.response import Response
from app.models.assets.bins import Bins
from app.serializers.assets.bins_serializer import BinsSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import datetime
from django.conf import settings
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets

def save_uploaded_file(file, folder_name):
    """
    Saves uploaded file inside MEDIA_ROOT/folder_name/
    Returns relative file path to store in DB
    """

    if not file:
        return None

    # Create folder path
    upload_dir = os.path.join(settings.MEDIA_ROOT, folder_name)

    os.makedirs(upload_dir, exist_ok=True)

    original_name = file.name.replace(" ", "_")
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{timestamp}_{original_name}"

    file_path = os.path.join(upload_dir, filename)

    # Save file manually
    with open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    # Return relative path (to store in DB)
    return os.path.join(folder_name, filename)



class BinsViewSet(AuditViewSetMixin, viewsets.ModelViewSet):

    parser_classes = (MultiPartParser, FormParser, JSONParser)

    serializer_class = BinsSerializer
    lookup_field = "unique_id"

    permission_resource = "Bin"

    AUDIT_MODULE = "assets"
    AUDIT_ENDPOINT ="bins"

    def create(self, request, *args, **kwargs):

        data = request.data.copy()

        image_file = request.FILES.get("bin_image")
        if image_file:
            image_path = save_uploaded_file(image_file, "bins")
            data["bin_image"] = image_path

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(serializer.data, status=201)
    
    def get_queryset(self):
        queryset = Bins.objects.select_related(
            "district_id",
            "collection_point_id",
            "collection_point_id__panchayat_id",
            "wastetype_id",
        ).filter(is_deleted=False)

        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        panchayat_uid = self.request.query_params.get("panchayat") or self.request.query_params.get("panchayat_id")
        collection_point_uid = (
            self.request.query_params.get("collection_point")
            or self.request.query_params.get("collection_point_id")
        )

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if panchayat_uid:
            queryset = queryset.filter(collection_point_id__panchayat_id__unique_id=panchayat_uid)

        if collection_point_uid:
            queryset = queryset.filter(collection_point_id__unique_id=collection_point_uid)

        return queryset
    
    def perform_destroy(self, instance):
        instance.delete()
