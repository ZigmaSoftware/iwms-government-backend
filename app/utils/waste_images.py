"""Helpers to surface waste-collection capture photos.

The photos are taken in the mobile capture flow and stored on
``WasteCollectionSub.image``. They are linked to a household collection only by
customer + date (there is no direct link), so these helpers resolve and build
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


def _capture_window(collection_date):
    """(start, end) of the ± 1 day window around `collection_date`."""
    start = _dt.datetime.combine(collection_date, _dt.time.min) - _dt.timedelta(days=1)
    end = _dt.datetime.combine(collection_date, _dt.time.max) + _dt.timedelta(days=1)
    if _tz.is_aware(_tz.now()):
        start = _tz.make_aware(start)
        end = _tz.make_aware(end)
    return start, end


def _capture_subs():
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import (
        WasteCollectionSub,
    )

    return (
        WasteCollectionSub.objects.filter(is_deleted=False)
        .exclude(image__isnull=True)
        .exclude(image="")
    )


def _image_dict(sub, request):
    url = build_media_url(sub.image, request)
    if not url:
        return None
    return {
        "url": url,
        "waste_type_id": sub.waste_type_id,
        "weight": sub.weight,
    }


def capture_images_for_customer(customer_id, collection_date=None, request=None):
    """Capture photos (``WasteCollectionSub``) for a household, linked by customer
    and — when supplied — the collection day (± 1 day to absorb timezone skew;
    a ``__date`` lookup is unreliable on MySQL without the tz tables loaded)."""
    subs = _capture_subs().filter(customer_id=customer_id)
    if collection_date:
        start, end = _capture_window(collection_date)
        subs = subs.filter(date_time__gte=start, date_time__lte=end)

    images = []
    for sub in subs.order_by("date_time"):
        image = _image_dict(sub, request)
        if image:
            images.append(image)
    return images


def capture_images_for_customers(pairs, request=None):
    """Bulk `capture_images_for_customer` for many (customer_id,
    collection_date) pairs in one query — for list pages, which would
    otherwise query once per household. Returns {pair: [image, ...]}."""
    pairs = {pair for pair in pairs if pair[0]}
    if not pairs:
        return {}
    subs = _capture_subs().filter(customer_id__in={customer_id for customer_id, _ in pairs})
    # Narrow the scan to the overall window when every pair has a date.
    if all(collection_date for _, collection_date in pairs):
        windows = [_capture_window(collection_date) for _, collection_date in pairs]
        subs = subs.filter(
            date_time__gte=min(start for start, _ in windows),
            date_time__lte=max(end for _, end in windows),
        )
    subs_by_customer = {}
    for sub in subs.order_by("date_time"):
        subs_by_customer.setdefault(sub.customer_id, []).append(sub)

    result = {}
    for customer_id, collection_date in pairs:
        window = _capture_window(collection_date) if collection_date else None
        images = []
        for sub in subs_by_customer.get(customer_id, []):
            if window and not (sub.date_time and window[0] <= sub.date_time <= window[1]):
                continue
            image = _image_dict(sub, request)
            if image:
                images.append(image)
        result[(customer_id, collection_date)] = images
    return result
