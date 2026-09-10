"""Face recognition for attendance, with a switchable backend.

Which engine runs is decided by one line in `.env`:

    FACE_RECOGNITION_PROVIDER=insightface     # on-server, no external API
    FACE_RECOGNITION_PROVIDER=compreface      # the hosted CompreFace API

Both stay fully supported. The register/recognise HTTP contract does not
change between them — same URLs, same form fields, same response shape — so
switching is a server-side env change and a restart, with no mobile release.
The app reads the active provider from `GET attendance/face-config/` if it
wants to show it, but does not need to know which is running to work.

Adding a third provider means implementing `FaceProvider` (see `base.py`) and
adding it to `_PROVIDERS` below; nothing in the viewsets should change.
"""

from __future__ import annotations

import logging
import threading

from django.conf import settings

from .base import (
    FaceError,
    FaceProvider,
    FaceUnavailable,
    ReferenceData,
    VerifyResult,
)
from .compre_face import CompreFaceProvider
from .insight_face import InsightFaceProvider

logger = logging.getLogger(__name__)

__all__ = [
    "FaceError",
    "FaceProvider",
    "FaceUnavailable",
    "ReferenceData",
    "VerifyResult",
    "get_provider",
    "active_provider_name",
    "available_providers",
    "reset_provider_cache",
]

DEFAULT_PROVIDER = "compreface"

_PROVIDERS = {
    "compreface": CompreFaceProvider,
    "insightface": InsightFaceProvider,
}

_instances: dict[str, FaceProvider] = {}
_instances_lock = threading.Lock()


def active_provider_name() -> str:
    """The provider named in settings, normalised and validated.

    An unrecognised value falls back to the default rather than raising, so a
    typo in `.env` degrades to "attendance still works on the old provider"
    instead of taking every punch down. The bad value is logged once per call
    site so it is visible in the server log.
    """
    raw = str(getattr(settings, "FACE_RECOGNITION_PROVIDER", "") or "").strip().lower()
    if not raw:
        return DEFAULT_PROVIDER
    if raw not in _PROVIDERS:
        logger.warning(
            "FACE_RECOGNITION_PROVIDER=%r is not one of %s — falling back to %r.",
            raw,
            sorted(_PROVIDERS),
            DEFAULT_PROVIDER,
        )
        return DEFAULT_PROVIDER
    return raw


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)


def get_provider(name: str | None = None) -> FaceProvider:
    """Return the shared instance of the active (or named) provider.

    Instances are cached per name: the InsightFace one holds a loaded model
    that must not be rebuilt per request, and the CompreFace one is stateless
    so sharing it costs nothing.
    """
    key = (name or active_provider_name()).strip().lower()
    if key not in _PROVIDERS:
        key = DEFAULT_PROVIDER

    instance = _instances.get(key)
    if instance is not None:
        return instance

    with _instances_lock:
        instance = _instances.get(key)
        if instance is None:
            instance = _PROVIDERS[key]()
            _instances[key] = instance
        return instance


def reset_provider_cache() -> None:
    """Drop cached instances — for tests that flip the provider setting."""
    with _instances_lock:
        _instances.clear()
