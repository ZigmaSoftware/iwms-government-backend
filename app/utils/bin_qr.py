import json
from io import BytesIO

import qrcode
from django.core.files.base import ContentFile


def generate_bin_qr_content(unique_id):
    payload = json.dumps({"id": unique_id}, ensure_ascii=False, separators=(",", ":"))

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue())
