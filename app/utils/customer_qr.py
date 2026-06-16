import json
import re
from io import BytesIO

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile

QR_SUBPROPERTY_APARTMENT = "apartment"
QR_SUBPROPERTY_VILLA = "villa"
QR_SUBPROPERTY_INDIVIDUAL_HOUSE = "individual_house"
QR_SUBPROPERTY_INDUSTRY = "industry"
QR_SUBPROPERTY_OTHER = "other"

QR_PAYLOAD_MODE_FULL = "full"
QR_PAYLOAD_MODE_ID_ONLY = "id"


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _drop_empty_fields(data):
    return {
        key: value
        for key, value in data.items()
        if value is not None and value != ""
    }


def _normalize_subproperty_name(name):
    cleaned = _clean_text(name)
    if not cleaned:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", cleaned.lower()).strip()


def resolve_subproperty_type(subproperty_name):
    normalized = _normalize_subproperty_name(subproperty_name)

    if "apartment" in normalized:
        return QR_SUBPROPERTY_APARTMENT
    if "villa" in normalized:
        return QR_SUBPROPERTY_VILLA
    if "industry" in normalized or "industrial" in normalized:
        return QR_SUBPROPERTY_INDUSTRY
    if (
        "individual house" in normalized
        or normalized == "house"
        or ("individual" in normalized and "house" in normalized)
    ):
        return QR_SUBPROPERTY_INDIVIDUAL_HOUSE

    return QR_SUBPROPERTY_OTHER


def generate_qr_data(instance):
    return {
        "id": _clean_text(getattr(instance, "unique_id", None))
    }

def generate_customer_qr_content(data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

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


# def generate_apartment_qr_data(apartment_name):
#     apartment_name = _clean_text(apartment_name)

#     if apartment_name:
#         apartment_id = f"APT-{apartment_name.replace(' ', '').upper()}"
#     else:
#         apartment_id = "APT-UNKNOWN"

#     return {
#         "apartment_id": apartment_id
#     }




def generate_apartment_qr_data(apartment_id):
    return {
        "apartment_id": apartment_id
    }