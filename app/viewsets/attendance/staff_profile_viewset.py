from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny

from app.models.user_creations.staffcreation import Staffcreation, StaffPersonalDetails
from app.serializers.attendance import (
    StaffOfficeSerializer,
    StaffUpdateSerializer,
)


class StaffProfileViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    # -----------------------------------
    # GET Profile
    # staff_id_id = User.staff_id_id (STRING)
    # maps to Staffcreation.staff_unique_id
    # -----------------------------------
    def list(self, request):
        staff_unique_id = request.query_params.get("staff_id_id")

        if not staff_unique_id:
            return Response(
                {"status": "error", "message": "staff_id_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            staff = Staffcreation.objects.select_related(
                "personal_details"
            ).get(staff_unique_id=staff_unique_id)
        except Staffcreation.DoesNotExist:
            return Response(
                {"status": "error", "message": "Staff profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = StaffOfficeSerializer(staff)
        return Response(
            {"status": "success", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    # -----------------------------------
    # UPDATE Profile (pk = Staffcreation.staff_unique_id)
    # -----------------------------------
    def update(self, request, pk=None):
        try:
            staff = Staffcreation.objects.get(staff_unique_id=pk)
        except Staffcreation.DoesNotExist:
            return Response(
                {"status": "error", "message": "Staff not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = StaffUpdateSerializer(
            staff, data=request.data, partial=True
        )

        if not serializer.is_valid():
            return Response(
                {"status": "error", "message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        # Update personal details
        dob = request.data.get("dob")
        blood_group = request.data.get("blood_group")

        personal, _ = StaffPersonalDetails.objects.get_or_create(
            staff=staff
        )
        if dob:
            personal.dob = dob
        if blood_group:
            personal.blood_group = blood_group
        personal.save()

        return Response(
            {"status": "success", "message": "Profile updated successfully"},
            status=status.HTTP_200_OK,
        )
