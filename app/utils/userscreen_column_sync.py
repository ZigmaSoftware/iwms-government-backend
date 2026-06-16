# =========================================================
# utils/userscreen_column_sync.py
# =========================================================
# DEPRECATED: This file is maintained for backward compatibility.
# Use app.services.schema_sync_service.sync_screen_columns instead.
# =========================================================

from app.services.schema_sync_service import sync_screen_columns as _sync_screen_columns


def sync_screen_columns(userscreen):
    """
    DEPRECATED: Use app.services.schema_sync_service.sync_screen_columns instead.

    Sync UserScreenColumn records with the actual Django model fields.
    This function is maintained for backward compatibility.
    """
    return _sync_screen_columns(userscreen)