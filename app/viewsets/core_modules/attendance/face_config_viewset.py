"""Tells the mobile app how attendance face capture is configured.

The point of this endpoint is that switching `FACE_RECOGNITION_PROVIDER` in
`.env` needs no mobile release. The register/recognise contract is identical
across providers, so the app does not strictly need this to work — but the
capture guidance does differ slightly (CompreFace rejects a reference photo
with a second face in frame; InsightFace additionally wants a face large
enough in the frame to embed), and hard-coding either engine's rules in the
app is exactly the coupling this avoids.

Read once at app start and cached client-side; it is cheap and unauthenticated
because it exposes nothing about any individual.
"""

from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.services import face_recognition


class FaceConfigViewSet(ViewSet):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description=(
            "Active attendance face-recognition provider and the capture rules "
            "the app should apply. Driven by FACE_RECOGNITION_PROVIDER in the "
            "server .env so the provider can be switched without an app release."
        )
    )
    def list(self, request):
        provider = face_recognition.get_provider()
        ready, reason = provider.health()

        return Response(
            {
                "provider": provider.name,
                "available_providers": face_recognition.available_providers(),
                # False means face register/punch will fail right now — the app
                # can say "attendance is temporarily unavailable" up front
                # instead of after the user has taken a selfie.
                "ready": ready,
                "reason": reason,
                # Informational only. The server always re-checks; never gate
                # the punch on this client-side, since the scale differs per
                # provider and the cutoff can be retuned server-side at will.
                "threshold": getattr(provider, "threshold", lambda: None)(),
                "capture": {
                    # Registration must be one face only under both providers.
                    "register_single_face_required": True,
                    "min_face_pixels": int(
                        _setting("FACE_MIN_PIXELS", 60)
                        if provider.name == "insightface"
                        else 0
                    ),
                    "guidance": (
                        "Face the camera in good light, with only your face in frame."
                    ),
                },
            }
        )


def _setting(name, default):
    from django.conf import settings

    return getattr(settings, name, default)
