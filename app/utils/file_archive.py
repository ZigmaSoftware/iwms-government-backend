"""Archive user-supplied files under MEDIA_ROOT so audits can reference them.

Bulk-uploaded CSVs and frontend-generated exports are stored here (never
trusted for execution — plain data files only) and their URLs are recorded
in the audit trail's ``new_data`` (``file_url`` / ``attachment_url``).
"""

import os
import re
import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_.-]+")


def safe_filename(filename: str, max_length: int = 80) -> str:
    base = os.path.basename(filename or "upload")
    cleaned = SAFE_CHARS.sub("_", base).strip("._") or "upload"
    if len(cleaned) > max_length:
        stem, dot, ext = cleaned.rpartition(".")
        cleaned = (stem[: max_length - len(ext) - 1] + dot + ext) if dot else cleaned[:max_length]
    return cleaned


def archive_bytes(content: bytes, filename: str, subdir: str = "audit_attachments") -> dict:
    """Store ``content`` under ``media/<subdir>/``; return url metadata.

    Never raises — callers must not fail the primary operation (upload,
    export) just because archiving failed; they get ``{"archived": False}``.
    """
    try:
        stamped = f"{int(time.time())}_{safe_filename(filename)}"
        stored = default_storage.save(f"{subdir}/{stamped}", ContentFile(content))
        url = default_storage.url(stored)
        # FileSystemStorage.url() already prefixes MEDIA_URL; be explicit
        # when a custom storage returns a bare path.
        if url and not str(url).startswith(("http://", "https://", "/")):
            url = f"{settings.MEDIA_URL.rstrip('/')}/{str(url).lstrip('/')}"
        return {
            "archived": True,
            "file_name": os.path.basename(stored),
            "original_name": filename,
            "file_url": url,
            "size": len(content),
        }
    except Exception as exc:
        return {"archived": False, "error": str(exc)}
