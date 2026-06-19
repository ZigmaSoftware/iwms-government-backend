from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.masters.panchayat import Panchayat
from app.models.masters.district import District
from app.models.common_masters.state import State
from app.models.common_masters.country import Country


@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny])
def property_data(request):
    api_key = request.META.get('HTTP_X_API_KEY', '').strip()

    if api_key != settings.MY_API_KEY:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    data = list(Property.objects.values())

    print(settings.MY_API_KEY)

    return Response({
        "status": "success",
        "data": data
    })




@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny])
def subproperty_data(request):
    api_key = request.META.get('HTTP_X_API_KEY', '').strip()

    if api_key != settings.MY_API_KEY:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    data = list(SubProperty.objects.values())

    print(settings.MY_API_KEY)

    return Response({
        "status": "success",
        "data": data
    })



@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny])
@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny])
def panchayat_data(request):
    api_key = request.META.get('HTTP_X_API_KEY', '').strip()

    if api_key != settings.MY_API_KEY:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    data = list(Panchayat.objects.values())

    print(settings.MY_API_KEY)

    return Response({
        "status": "success",
        "data": data
    })


@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny])
def district_data(request):
    api_key = request.META.get('HTTP_X_API_KEY', '').strip()

    if api_key != settings.MY_API_KEY:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    data = list(District.objects.values())

    print(settings.MY_API_KEY)

    return Response({
        "status": "success",
        "data": data
    })



@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny])
def state_data(request):
    api_key = request.META.get('HTTP_X_API_KEY', '').strip()

    if api_key != settings.MY_API_KEY:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    data = list(State.objects.values())

    print(settings.MY_API_KEY)

    return Response({
        "status": "success",
        "data": data
    })



@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny])
def country_data(request):
    api_key = request.META.get('HTTP_X_API_KEY', '').strip()

    if api_key != settings.MY_API_KEY:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    data = list(Country.objects.values())

    print(settings.MY_API_KEY)

    return Response({
        "status": "success",
        "data": data
    })
