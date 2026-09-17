"""
Test-only settings.

Inherits production settings but overrides the database with SQLite in-memory
so tests run fast, portable, and without needing MySQL.

SECRET_KEY must be set early (before the wildcard import) so that
settings_jwt.py can access it via django.conf.settings during the
re-entrant module load triggered by the LazySettings proxy.
"""
import os
from dotenv import load_dotenv

# Load .env so SECRET_KEY and other vars are in os.environ
load_dotenv()

# Expose SECRET_KEY as a module attribute BEFORE the wildcard import.
# When settings_jwt.py accesses django.conf.settings.SECRET_KEY during
# the circular load, Django re-reads this partial module and needs to
# find SECRET_KEY already defined here.
SECRET_KEY = os.getenv("SECRET_KEY", "insecure-test-secret-key-not-for-production")

from .settings import * 

# ── Override database ───────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
        "OPTIONS": {},
        "TIME_ZONE": None,
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": False,
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
        "TEST": {},
    }
}

# ── Faster password hashing in tests ───────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ── Disable migrations so syncdb creates ALL tables (incl. unmanaged helpers) ─
MIGRATION_MODULES = {
    "app": None,
}

# ── In-memory cache for tests ───────────────────────────────────────
# Tests must not depend on (or pollute) a real Redis instance. Both
# aliases point at independent LocMemCache instances so throttling
# (CACHES["default"]) and app.cache (CACHES["app_cache"]) stay isolated
# from each other, matching production's separate-db setup.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-throttle-cache",
    },
    "app_cache": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-app-cache",
    },
}

# ── Disable rate limiting in tests ──────────────────────────────────
# Cache/API tests exercise the same endpoint many times in a row; the
# real per-scope throttle rates (config/throttle_rates.py) would produce
# spurious 429s unrelated to whatever the test is actually checking.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}
