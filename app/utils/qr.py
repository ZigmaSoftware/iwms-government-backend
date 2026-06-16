import qrcode
import os
from django.conf import settings

def generate_qr(emp_id, name, timestamp):
    """
    Generates a QR code PNG file and saves it under media/qrcodes/.
    Returns the QR filename (not full path) so it can be stored in DB.
    """

    qr_data = f"ID: {emp_id}\nName: {name}"
    filename = f"{name}{emp_id}{timestamp}.png"

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