"""Helpers to surface waste-collection capture photos.

The photos are taken in the mobile capture flow and stored on
``WasteCollectionSub.image``. They are linked to a household collection only by
customer + date (there is no direct FK), so these helpers resolve and build
servable ``/media/`` URLs for both the WasteCollection and DailyTripLog
serializers.
"""

import datetime as _dt

from django.conf import settings
from django.utils import timezone as _tz


def build_media_url(image, request=None):
    """Build a servable media URL from a stored image path.

    The mobile uploader stores paths like ``uploads/waste_collection_images/<f>``
    even though the file is served from ``MEDIA_URL + 'waste_collection_images/'``,
    so rebuild the URL from the filename to avoid the stale ``uploads/`` prefix.
    """
    if not image:
        return None
    image = str(image)
    if image.startswith("http"):
        return image
    filename = image.rstrip("/").split("/")[-1]
    path = f"{settings.MEDIA_URL}waste_collection_images/{filename}"
    return request.build_absolute_uri(path) if request is not None else path


def capture_images_for_customer(customer_id, collection_date=None, request=None):
    """Capture photos (``WasteCollectionSub``) for a household, linked by customer
    and — when supplied — the collection day (± 1 day to absorb timezone skew;
    a ``__date`` lookup is unreliable on MySQL without the tz tables loaded)."""
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import (
        WasteCollectionSub,
    )

    subs = (
        WasteCollectionSub.objects.filter(customer_id=customer_id, is_deleted=False)
        .exclude(image__isnull=True)
        .exclude(image="")
    )
    if collection_date:
        start = _dt.datetime.combine(collection_date, _dt.time.min) - _dt.timedelta(days=1)
        end = _dt.datetime.combine(collection_date, _dt.time.max) + _dt.timedelta(days=1)
        if _tz.is_aware(_tz.now()):
            start = _tz.make_aware(start)
            end = _tz.make_aware(end)
        subs = subs.filter(date_time__gte=start, date_time__lte=end)

    images = []
    for sub in subs.order_by("date_time"):
        url = build_media_url(sub.image, request)
        if url:
            images.append({
                "url": url,
                "waste_type_id": sub.waste_type_id,
                "weight": sub.weight,
            })
    return images
