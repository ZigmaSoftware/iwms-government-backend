"""InsightFace provider — recognition running inside this server.

Selected with `FACE_RECOGNITION_PROVIDER=insightface`. No third-party face
API and no per-punch network round trip: the model is loaded once per worker
process and reused.

SIMILARITY SCALE (important)
---------------------------
This returns raw **cosine similarity between L2-normalised ArcFace
embeddings**. Genuine matches typically land around 0.45-0.75 and different
people around 0.0-0.25. CompreFace's 0.95 cutoff means something completely
different and must NOT be carried over — the default here is 0.5
(`FACE_MATCH_THRESHOLD`) and should be tuned against real punch photos.

RESOURCE USE
------------
Under gunicorn every worker that serves a punch loads its own copy of the
model, so `FACE_ONNX_THREADS` caps the CPU threads a single inference may
take. Without it one shift-start burst can starve the rest of the API.

LICENSING
---------
The InsightFace *library* is MIT. The *pretrained model packs* it downloads
(`buffalo_s`, `buffalo_l`, ...) are published for non-commercial research
use, which is a separate question from this code and has to be settled for
whichever pack is configured.
"""

from __future__ import annotations

import io
import logging
import os
import threading

from django.conf import settings

from .base import (
    FaceError,
    FaceProvider,
    FaceUnavailable,
    ReferenceData,
    VerifyResult,
)

logger = logging.getLogger(__name__)


def _thread_cap() -> int:
    try:
        return max(1, int(getattr(settings, "FACE_ONNX_THREADS", 2) or 2))
    except (TypeError, ValueError):
        return 2


# Thread caps have to be in the environment before onnxruntime/OpenCV are
# imported, or they latch onto every core and one selfie stalls the worker.
def _apply_thread_limits() -> None:
    cap = str(_thread_cap())
    for var in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(var, cap)


_model = None
_model_error: Exception | None = None
_model_lock = threading.Lock()


# numpy / OpenCV / insightface are imported lazily, never at module scope.
# This module is imported by the package `__init__` regardless of which
# provider is selected, so a top-level import would take down every
# attendance endpoint — CompreFace included — on any server that has not
# installed the (optional) InsightFace dependencies.
def _np():
    try:
        import numpy

        return numpy
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise FaceUnavailable(
            "Face recognition is unavailable: the InsightFace dependencies are "
            "not installed on this server."
        ) from exc


def _cv2():
    """Import OpenCV lazily, after the thread caps are in place."""
    _apply_thread_limits()
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise FaceUnavailable(
            "Face recognition is unavailable: the InsightFace dependencies are "
            "not installed on this server."
        ) from exc

    try:
        cv2.setNumThreads(_thread_cap())
    except Exception:  # pragma: no cover - older OpenCV builds
        pass
    return cv2


def _load_model():
    """Return the shared FaceAnalysis app, or None if it could not load.

    A failure is remembered rather than retried, so a broken install (missing
    pack, no disk space for the download) does not pay the same timeout on
    every punch.
    """
    global _model, _model_error

    if _model is not None or _model_error is not None:
        return _model

    with _model_lock:
        if _model is not None or _model_error is not None:
            return _model

        try:
            _apply_thread_limits()
            from insightface.app import FaceAnalysis

            name = getattr(settings, "FACE_MODEL_NAME", "buffalo_s")
            root = getattr(settings, "FACE_MODEL_ROOT", "") or None
            det_size = int(getattr(settings, "FACE_DET_SIZE", 640) or 640)

            kwargs = {"name": name, "providers": ["CPUExecutionProvider"]}
            if root:
                kwargs["root"] = root

            # Detection + recognition only; the age/gender/landmark modules
            # are unused here and cost both load time and RAM.
            app = FaceAnalysis(allowed_modules=["detection", "recognition"], **kwargs)
            app.prepare(ctx_id=-1, det_size=(det_size, det_size))

            _model = app
            logger.info("InsightFace model '%s' ready (det_size=%s)", name, det_size)
        except Exception as exc:  # pragma: no cover - depends on local install
            _model_error = exc
            logger.exception(
                "InsightFace failed to load; attendance face calls will report "
                "the service as unavailable until this is fixed."
            )

    return _model


def _normalise(vector) -> list[float]:
    np = _np()
    arr = np.asarray(vector, dtype=np.float32).ravel()
    norm = float(np.linalg.norm(arr))
    if not np.isfinite(norm) or norm == 0.0:
        raise FaceError("Face not clear enough. Please retake the photo.")
    return (arr / norm).astype(np.float32).tolist()


def _bbox_area(bbox) -> float:
    x1, y1, x2, y2 = [float(v) for v in bbox]
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


class InsightFaceProvider(FaceProvider):
    name = "insightface"

    def threshold(self) -> float:
        return float(getattr(settings, "FACE_MATCH_THRESHOLD", 0.5) or 0.5)

    def health(self) -> tuple[bool, str | None]:
        if _load_model() is not None:
            return True, None
        error = _model_error
        return False, f"InsightFace model failed to load: {error}" if error else "not loaded"

    # -- image handling -------------------------------------------------

    def _decode(self, raw: bytes):
        """Decode uploaded bytes to a BGR array the detector can read.

        Honours the EXIF orientation tag: phone selfies are very often stored
        rotated, and a sideways face simply is not detected.
        """
        if not raw:
            raise FaceError("No image received. Please retake the photo.")

        # Resolved before the try block on purpose: these raise
        # FaceUnavailable (a FaceError subclass) when the optional deps are
        # missing, and the blanket `except Exception` below would otherwise
        # rewrite that into "retake the photo" — a 400 blaming the user for a
        # server-side install problem that should be a 503.
        cv2 = _cv2()
        np = _np()
        try:
            from PIL import Image, ImageOps

            pil = Image.open(io.BytesIO(raw))
            pil = ImageOps.exif_transpose(pil)
            pil = pil.convert("RGB")
            frame = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        except Exception as exc:
            raise FaceError("That image could not be read. Please retake the photo.") from exc

        if frame is None or frame.size == 0:
            raise FaceError("That image could not be read. Please retake the photo.")

        # Cap the long edge, preserving aspect ratio. A 12MP phone photo is
        # far larger than the detector needs and costs real time; squashing it
        # to a fixed 640x480 would distort faces instead.
        max_edge = int(getattr(settings, "FACE_MAX_IMAGE_EDGE", 1280) or 1280)
        height, width = frame.shape[:2]
        longest = max(height, width)
        if longest > max_edge:
            scale = max_edge / float(longest)
            frame = cv2.resize(
                frame,
                (int(round(width * scale)), int(round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        return frame

    def _sharpness(self, crop) -> float:
        """Variance of the Laplacian — a blur measure, NOT liveness.

        This rejects out-of-focus and motion-blurred selfies, which produce
        unreliable embeddings. It does not detect a photo of a photo or a face
        held up on a phone screen: a sharp spoof scores just as well as a real
        face. Anti-spoofing needs a purpose-built PAD model, which this isn't.
        """
        if crop is None or crop.size == 0:
            return 0.0
        cv2 = _cv2()
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _crop(self, frame, bbox, margin: float = 0.2):
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        dx = int((x2 - x1) * margin)
        dy = int((y2 - y1) * margin)
        x1 = max(0, x1 - dx)
        y1 = max(0, y1 - dy)
        x2 = min(width, x2 + dx)
        y2 = min(height, y2 + dy)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    def embed(self, raw: bytes, *, require_single_face: bool = False) -> list[float]:
        """Raw image bytes -> L2-normalised face embedding.

        `require_single_face` is used at registration: a reference photo with
        a colleague in the background would otherwise silently enrol the wrong
        person. At punch time it stays off and the largest face wins, because
        people queue up behind each other at the punch point.
        """
        app = _load_model()
        if app is None:
            raise FaceUnavailable(
                "Face recognition is unavailable. Please contact your administrator."
            )

        frame = self._decode(raw)
        faces = app.get(frame)
        if not faces:
            raise FaceError(
                "No face detected. Please face the camera in good light and retake."
            )

        if require_single_face and len(faces) > 1:
            raise FaceError(
                "More than one face detected. Please retake with only your face in the frame."
            )

        face = max(faces, key=lambda f: _bbox_area(f.bbox))

        min_det = float(getattr(settings, "FACE_MIN_DET_SCORE", 0.5) or 0.5)
        if float(getattr(face, "det_score", 1.0)) < min_det:
            raise FaceError(
                "No face detected. Please face the camera in good light and retake."
            )

        min_px = int(getattr(settings, "FACE_MIN_PIXELS", 60) or 60)
        x1, y1, x2, y2 = [int(v) for v in face.bbox]
        if (x2 - x1) < min_px or (y2 - y1) < min_px:
            raise FaceError("Face is too small in the frame. Please hold the camera closer.")

        min_sharpness = float(getattr(settings, "FACE_MIN_SHARPNESS", 0.0) or 0.0)
        if min_sharpness > 0 and self._sharpness(self._crop(frame, face.bbox)) < min_sharpness:
            raise FaceError("Photo is too blurry. Hold still and retake it.")

        vector = getattr(face, "normed_embedding", None)
        if vector is None:
            vector = getattr(face, "embedding", None)
        if vector is None:
            raise FaceError("Face not clear enough. Please retake the photo.")
        return _normalise(vector)

    def similarity(self, a, b) -> float:
        """Cosine similarity, clamped to [-1, 1].

        Both sides are re-normalised rather than trusted: one of them comes
        back out of the database, where an older build may have written it.
        """
        np = _np()
        left = np.asarray(_normalise(a), dtype=np.float32)
        right = np.asarray(_normalise(b), dtype=np.float32)
        if left.shape != right.shape:
            raise FaceError("Stored face data is out of date. Please register your face again.")
        return float(np.clip(np.dot(left, right), -1.0, 1.0))

    # -- provider interface ---------------------------------------------

    def validate_reference(self, image_bytes: bytes) -> ReferenceData:
        return ReferenceData(embedding=self.embed(image_bytes, require_single_face=True))

    def verify(
        self,
        captured_bytes: bytes,
        *,
        reference_path: str | None,
        reference_embedding: list[float] | None,
    ) -> VerifyResult:
        stored = reference_embedding
        derived: list[float] | None = None

        # Staff enrolled while CompreFace was active have a reference image
        # but no embedding. Rather than force everyone to re-register the day
        # this is switched on, derive it from the image already on file and
        # hand it back on the result so the caller can persist it — after
        # which this path is never taken again for that person.
        if not stored:
            if not reference_path:
                raise FaceError("Staff attendance image is not registered")
            try:
                with open(reference_path, "rb") as handle:
                    reference_bytes = handle.read()
            except OSError as exc:
                raise FaceError(f"Source image not found: {reference_path}") from exc
            stored = self.embed(reference_bytes, require_single_face=False)
            derived = stored

        captured = self.embed(captured_bytes, require_single_face=False)
        score = self.similarity(captured, stored)
        threshold = self.threshold()
        return VerifyResult(
            matched=score >= threshold,
            score=score,
            threshold=threshold,
            derived_embedding=derived,
        )
