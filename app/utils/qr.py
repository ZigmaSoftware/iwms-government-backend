import os
import re

import qrcode
from django.conf import settings


def _safe_component(value, fallback="x"):
    """Filesystem-safe slug for a filename component. Staff names can contain
    spaces, dots or slashes that would break the QR file save (and 500 the
    register endpoint), so strip them out and bound the length."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    return (slug[:40] or fallback)


def generate_qr(emp_id, name, timestamp):
    """
    Generates a QR code PNG file and saves it under media/qrcodes/.
    Returns the QR filename (not full path) so it can be stored in DB.
    """

    # QR *content* keeps the real name; only the on-disk filename is sanitized.
    qr_data = f"ID: {emp_id}\nName: {name}"
    filename = f"{_safe_component(name)}_{_safe_component(emp_id)}_{timestamp}.png"

    # Create qrcodes folder if not exists
    qr_folder = os.path.join(settings.MEDIA_ROOT, "qrcodes")
    os.makedirs(qr_folder, exist_ok=True)

    filepath = os.path.join(qr_folder, filename)

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filepath)

    return filename