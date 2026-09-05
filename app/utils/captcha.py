"""Self-hosted text captcha: no external service/API key required.

Generates a short random code as a noisy PNG, keeps the expected value
server-side in the default cache keyed by a one-time id, and lets a
verifier check-and-burn that id. Login viewsets call `verify_captcha`
before validating credentials so every login surface shares one policy.
"""
import io
import random
import string
import uuid
import base64

from django.core.cache import cache
from PIL import Image, ImageDraw, ImageFont

CAPTCHA_CACHE_PREFIX = "captcha:"
CAPTCHA_TTL_SECONDS = 5 * 60
CAPTCHA_LENGTH = 5
CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity

_IMAGE_WIDTH = 168
_IMAGE_HEIGHT = 56


def _cache_key(captcha_id):
    return f"{CAPTCHA_CACHE_PREFIX}{captcha_id}"


def _render_image(code):
    image = Image.new("RGB", (_IMAGE_WIDTH, _IMAGE_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
    except OSError:
        font = ImageFont.load_default()

    for _ in range(6):
        start = (random.randint(0, _IMAGE_WIDTH), random.randint(0, _IMAGE_HEIGHT))
        end = (random.randint(0, _IMAGE_WIDTH), random.randint(0, _IMAGE_HEIGHT))
        draw.line([start, end], fill=(random.randint(150, 200),) * 3, width=1)

    cursor_x = 14
    for char in code:
        y_jitter = random.randint(-3, 3)
        draw.text((cursor_x, 12 + y_jitter), char, font=font, fill=(random.randint(0, 80),) * 3)
        cursor_x += 30

    for _ in range(80):
        xy = (random.randint(0, _IMAGE_WIDTH), random.randint(0, _IMAGE_HEIGHT))
        draw.point(xy, fill=(random.randint(100, 180),) * 3)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_captcha():
    """Create a new captcha, store its answer, and return id + PNG data URI."""
    code = "".join(random.choices(CAPTCHA_ALPHABET, k=CAPTCHA_LENGTH))
    captcha_id = uuid.uuid4().hex

    cache.set(_cache_key(captcha_id), code, timeout=CAPTCHA_TTL_SECONDS)

    png_bytes = _render_image(code)
    image_data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    return {
        "captcha_id": captcha_id,
        "image": image_data_uri,
        "expires_in": CAPTCHA_TTL_SECONDS,
    }


def verify_captcha(captcha_id, value):
    """Check `value` against the stored answer for `captcha_id`.

    One-time use: the stored answer is deleted whether or not it matches,
    so a captured/replayed request can't be retried against the same code.
    """
    if not captcha_id or not value:
        return False

    key = _cache_key(captcha_id)
    expected = cache.get(key)
    cache.delete(key)

    if not expected:
        return False

    return expected.strip().upper() == value.strip().upper()
