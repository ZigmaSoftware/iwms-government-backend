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

from .settings import *  # noqa: F401, F403, E402

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
