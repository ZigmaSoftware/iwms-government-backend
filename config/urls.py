from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static

# Swagger imports
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny



from app.apis.property_api import property_data, subproperty_data, panchayat_data, district_data, state_data, country_data

def home(request):
    return HttpResponse("Django backend is running! Try /api/v1/")

def platform_console(request):
    return render(request, "platform_console.html")

#  Swagger schema with JWT support
schema_view = get_schema_view(
    openapi.Info(
        title="IWMS Backend API",
        default_version="v1",
        description="IWMS API with JWT Authentication",
    ),
    public=True,
    permission_classes=(AllowAny,),
)


urlpatterns = [
    # Home
    path("", home),
    path("platform/", platform_console),
    path("admin/", admin.site.urls),

    # APIs
    path("api/v1/", include("app.urls.base_urls")),

    # Swagger UI
    path(
        "api/v1/swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="swagger-ui",
    ),

    # Data endpoints for BP

    path("apis/property/", property_data, name="property-data"),
    path("apis/subproperty/", subproperty_data, name="subproperty-data"),
    path("apis/panchayat/", panchayat_data, name="panchayat-data"),
    path("apis/district/", district_data, name="district-data"),
    path("apis/state/", state_data, name="state-data"),
    path("apis/country/", country_data, name="country-data"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
