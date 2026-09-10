"""Shared pieces every face-recognition provider needs.

The provider interface here is deliberately small: attendance only ever asks
two things — "is this enrolment photo usable?" and "is this punch selfie the
same person as the one on file?". Everything else (where the reference image
lives, whether a similarity number means 0.95 or 0.5) is the provider's own
business, so swapping providers never reaches the viewsets.
"""

from __future__ import annotations

from dataclasses import dataclass


class FaceError(Exception):
    """A face could not be read or matched, with a user-facing reason.

    The message reaches the person taking the selfie, so it should say what
    to do differently rather than what failed internally.
    """


class FaceUnavailable(FaceError):
    """The provider itself is down or misconfigured — not the user's fault.

    Separated from FaceError so the viewsets can answer 503 (try again later)
    instead of 400 (your photo was no good), which matters when a provider is
    mid-outage and every punch would otherwise look like a rejected face.
    """


@dataclass(frozen=True)
class ReferenceData:
    """What registration produced and the staff row should persist.

    `embedding` is None for providers that re-read the stored image on every
    verify (CompreFace) and a 512-float vector for providers that compare
    vectors (InsightFace). Keeping it optional is what lets one column serve
    both without the viewset knowing which is active.
    """

    embedding: list[float] | None = None


@dataclass(frozen=True)
class VerifyResult:
    matched: bool
    score: float
    threshold: float

    #: Set when the provider had to derive the reference embedding during
    #: this call (a staff member enrolled under a provider that stores no
    #: embedding). The caller persists it so the work happens only once.
    #: Returned on the result rather than stashed on the provider, which is a
    #: process-wide singleton — a shared attribute would race between
    #: concurrent punches and could save one person's face onto another's row.
    derived_embedding: list[float] | None = None


class FaceProvider:
    """Interface both providers implement."""

    #: Short identifier reported to clients via the face-config endpoint.
    name: str = "unknown"

    def health(self) -> tuple[bool, str | None]:
        """(is_usable, reason_if_not) — used by the face-config endpoint."""
        raise NotImplementedError

    def validate_reference(self, image_bytes: bytes) -> ReferenceData:
        """Check an enrolment photo is usable; return anything to persist.

        Raises FaceError when the photo cannot be enrolled (no face, several
        faces, too blurry).
        """
        raise NotImplementedError

    def verify(
        self,
        captured_bytes: bytes,
        *,
        reference_path: str | None,
        reference_embedding: list[float] | None,
    ) -> VerifyResult:
        """Compare a punch selfie against the stored reference.

        Providers get both forms of reference and use whichever they support,
        because a staff member enrolled under one provider must still be able
        to punch after the other is switched on.
        """
        raise NotImplementedError
