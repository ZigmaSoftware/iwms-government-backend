from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from app.utils.captcha import generate_captcha


class CaptchaViewSet(ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        return Response(generate_captcha())
