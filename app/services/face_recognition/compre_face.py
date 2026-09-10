"""CompreFace provider — the original hosted face API.

This is the behaviour attendance has always had, lifted out of
`register_viewset` / `recognize_viewset` unchanged so it stays available as a
switchable option: set `FACE_RECOGNITION_PROVIDER=compreface`.

The endpoint and API key used to be hardcoded in the viewsets; they now come
from settings so the server can be repointed (or the key rotated) without a
code change.

Nothing is stored per staff member here — CompreFace compares two images on
every call, so verification re-reads the enrolment photo from disk each time.
That is also why it needs `reference_path` and ignores `reference_embedding`.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from .base import (
    FaceError,
    FaceProvider,
    FaceUnavailable,
    ReferenceData,
    VerifyResult,
)

logger = logging.getLogger(__name__)


def _describe_failure(data) -> str:
    """Turn a CompreFace response into something worth showing a user.

    Preserved verbatim from the original `_verification_error` in
    `recognize_viewset` — these strings are what the app already surfaces.
    """
    if not isinstance(data, dict):
        return "Face API invalid response"

    message = str(data.get("message") or "").strip()
    lower = message.lower()
    code = data.get("code")
    if code == 31 or "more than one face in the source" in lower:
        return (
            "Registered face has more than one face. "
            "Please re-register with only your face in the frame."
        )
    if "more than one face in the target" in lower:
        return "More than one face detected in the punch selfie. Please try again alone in the frame."
    if "more than one face" in lower:
        return "More than one face detected. Please try again with only your face in the frame."

    result = data.get("result")
    if isinstance(result, list) and result:
        first = result[0] if isinstance(result[0], dict) else {}
        if first.get("source_image_face") and not first.get("face_matches"):
            return "Face Similarity Not Matched"
        if first.get("face_matches") is None:
            return "Face not detected clearly. Please face the camera and try again."

    return message or "Face not detected"


class CompreFaceProvider(FaceProvider):
    name = "compreface"

    def _url(self) -> str:
        return getattr(settings, "COMPREFACE_VERIFY_URL", "")

    def _headers(self) -> dict:
        return {"x-api-key": getattr(settings, "COMPREFACE_API_KEY", "")}

    def _timeout(self) -> int:
        return int(getattr(settings, "COMPREFACE_TIMEOUT", 30) or 30)

    def threshold(self) -> float:
        # CompreFace returns its own 0-1 confidence, on which 0.95 has always
        # been the accepted cutoff here. It is NOT comparable to the cosine
        # similarity InsightFace reports — see that provider's own default.
        return float(getattr(settings, "COMPREFACE_MATCH_THRESHOLD", 0.95) or 0.95)

    def health(self) -> tuple[bool, str | None]:
        if not self._url():
            return False, "COMPREFACE_VERIFY_URL is not set."
        if not getattr(settings, "COMPREFACE_API_KEY", ""):
            return False, "COMPREFACE_API_KEY is not set."
        return True, None

    def _post(self, source_bytes: bytes, target_bytes: bytes) -> dict:
        ok, reason = self.health()
        if not ok:
            raise FaceUnavailable(f"Face recognition is not configured. {reason}")

        try:
            response = requests.post(
                self._url(),
                headers=self._headers(),
                files={
                    "source_image": ("source.jpg", source_bytes, "image/jpeg"),
                    "target_image": ("target.jpg", target_bytes, "image/jpeg"),
                },
                timeout=self._timeout(),
            )
        except requests.RequestException as exc:
            logger.warning("CompreFace request failed: %s", exc)
            raise FaceUnavailable(
                "Face recognition service is unreachable. Please try again shortly."
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise FaceError("Face API invalid response") from exc

    def validate_reference(self, image_bytes: bytes) -> ReferenceData:
        """Verify the enrolment photo against itself.

        A self-comparison is how the original code checked a reference photo
        held exactly one clearly-detected face — CompreFace has no standalone
        "is this one good face?" call, so this stays as it was.
        """
        data = self._post(image_bytes, image_bytes)

        message = str(data.get("message") or "").lower() if isinstance(data, dict) else ""
        code = data.get("code") if isinstance(data, dict) else None
        if code == 31 or "more than one face" in message:
            return _reject("More than one face detected. Register with only one face in the frame.")

        try:
            data["result"][0]["source_image_face"]
            data["result"][0]["face_matches"][0]
        except (KeyError, IndexError, TypeError):
            return _reject(
                "Face not detected clearly. Register in good light, facing the camera."
            )

        # Nothing to persist: verification re-reads the saved image each time.
        return ReferenceData(embedding=None)

    def verify(
        self,
        captured_bytes: bytes,
        *,
        reference_path: str | None,
        reference_embedding: list[float] | None,
    ) -> VerifyResult:
        if not reference_path:
            raise FaceError("Staff attendance image is not registered")

        try:
            with open(reference_path, "rb") as handle:
                source_bytes = handle.read()
        except OSError as exc:
            raise FaceError(f"Source image not found: {reference_path}") from exc

        data = self._post(source_bytes, captured_bytes)

        try:
            score = float(data["result"][0]["face_matches"][0]["similarity"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise FaceError(_describe_failure(data))

        threshold = self.threshold()
        return VerifyResult(matched=score >= threshold, score=score, threshold=threshold)


def _reject(message: str):
    raise FaceError(message)
