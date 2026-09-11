from pathlib import Path
import os
import pymysql
import warnings
from dotenv import load_dotenv

# drf-yasg 1.21.7 still imports pkg_resources internally. Setuptools emits
# this deprecation notice on every development-server reload; suppress only
# that known third-party warning while leaving all other warnings visible.
warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module=r"drf_yasg(\..*)?",
)

load_dotenv()
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent
from django.conf import settings

# -------------------------------------------------------
# SECRET KEY – use this one only (your exact key)
# -------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")

# DEBUG = True

# -------------------------------------------------------
# ENVIRONMENT CONFIG
# -------------------------------------------------------
ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
DEBUG = ENVIRONMENT != "production"
TRIP_ATTENDANCE_COOLDOWN_MINUTES = int(
    os.getenv("TRIP_ATTENDANCE_COOLDOWN_MINUTES", "1")
)


MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '192.168.1.128',
    '192.168.4.10',
    '.trycloudflare.com',
    '192.168.4.*',
    '192.168.5.*',
    '192.168.5.92',
    "125.17.238.158",
    '10.80.216.123',
    '192.168.4.58',
    '115.245.93.26',
    'testserver',
    '10.64.151.226',
    '10.205.101.232',
    '10.244.208.158',
    '10.183.250.158',  
    '192.168.5.92',
    '192.168.7.176',
    '192.168.5.77',
    '192.168.5.20',
    '192.168.6.198',
    '192.168.1.156',
    '192.168.3.120',
    '10.152.141.197',
    '192.168.3.112',
    '192.168.5.240', #sathya ip addr
    '10.245.75.197',
    '10.255.70.197',
    '192.168.6.238',
    '10.128.67.197',
    "aura-haustorial-elayne.ngrok-free.dev",
]

# -------------------------------------------------------
# Installed Apps
# -------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',

    # Your apps
    'app.apps.ApiConfig',
]

# -------------------------------------------------------
# Middleware
# -------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    'app.middleware.module_permission_middleware.ModulePermissionMiddleware',
    'app.middleware.request_meta_middleware.RequestMetaMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {   
    'default': {
        'ENGINE': os.getenv("DB_ENGINE", "django.db.backends.mysql"),
        'NAME': os.getenv("DB_NAME", "iwmsdbGovernment"), 
        'USER': os.getenv("DB_USER", "root"),
        'PASSWORD': os.getenv("DB_PASSWORD", "admin@123"),
        'HOST': os.getenv("DB_HOST", "localhost"),
        'PORT': os.getenv("DB_PORT", "3306"),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,

    "SECURITY_DEFINITIONS": {
        "Password": {
            "type": "oauth2",
            "flow": "password",
            "tokenUrl": "/api/v1/login/",
            "scopes": {},
            "description": "Login with username/password to auto-fill the Bearer token.",
        },
    },

    "OAUTH2_CONFIG": {
        "appName": "IWMS API",
    },

    # This is IMPORTANT for your grouped router
    "DEFAULT_AUTO_SCHEMA_CLASS": "app.utils.swagger.GroupedSwaggerAutoSchema",

    "TAGS_SORTER": "alpha",
}

# -------------------------------------------------------
# Password Validators
# -------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -------------------------------------------------------
# Internationalization
# -------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------
# Static Files
# -------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

ENABLE_AUTH_USER_SEEDING = os.getenv("ENABLE_AUTH_USER_SEEDING", "true").lower() == "true"

# -------------------------------------------------------
# Rate limiting (Redis-backed via CACHES["default"] above)
# -------------------------------------------------------
# Every DRF view has its own `throttle_scope` (set on the view class) so it
# gets an independent Redis counter/limit. Edit the number on the right to
# change that one API's request count — nothing else needs to change.
API_THROTTLE_RATES = {
    # Auth / sensitive endpoints — tighter limits
    'login': '10/minute',
    'otp': '5/minute',
    'reset_password': '5/minute',
    'change_password': '5/minute',
    'admin_change_password': '5/minute',

    # Everything else — default rate, tune individually as needed
    "administrative_hierarchy": "5/minute",
    "alternative_staff_template": "5/minute",
    "app_module": "5/minute",
    "area_type": "5/minute",
    "attendance_records": "5/minute",
    "audit_log": "5/minute",
    "bin_collection_event": "5/minute",
    "bins": "5/minute",
    "block_panchayat_union": "5/minute",
    "captcha": "5/minute",
    "citizen_complaint_ticket": "5/minute",
    "collection_point": "5/minute",
    "common_audit": "5/minute",
    "company_user_screen_column_permission": "5/minute",
    "complaint_address_change": "5/minute",
    "complaint_category": "5/minute",
    "complaint_feedback": "5/minute",
    "complaint_language": "5/minute",
    "complaint_module": "5/minute",
    "complaint_notification": "5/minute",
    "complaint_priority": "5/minute",
    "complaint_reopen_history": "5/minute",
    "complaint_routing_rule": "5/minute",
    "complaint_sla_rule": "5/minute",
    "complaint_source": "5/minute",
    "complaint_status": "5/minute",
    "complaint_subcategory": "5/minute",
    "complaint_team": "5/minute",
    "complaint_ticket": "5/minute",
    "continent": "5/minute",
    "contractor_user_type": "5/minute",
    "corporation": "5/minute",
    "country": "5/minute",
    "customer_access_configuration": "5/minute",
    "customer_creation": "5/minute",
    "daily_attendance_reg": "5/minute",
    "daily_trip_assignment": "5/minute",
    "daily_trip_collection_point": "5/minute",
    "daily_trip_household_collection": "5/minute",
    "daily_trip_log": "5/minute",
    "daily_waste_comparison": "5/minute",
    "dashboard_summary": "5/minute",
    "dashboard_widget_permission": "5/minute",
    "department": "5/minute",
    "designation": "5/minute",
    "district": "5/minute",
    "district_body_dashboard": "5/minute",
    "district_leader_login": "5/minute",
    "feed_back": "5/minute",
    "fuel": "5/minute",
    "government_staff_user_type": "5/minute",
    "local_body_dashboard": "5/minute",
    "login_audit": "5/minute",
    "main_screen": "5/minute",
    "main_screen_type": "5/minute",
    "monthly_waste_comparison_report": "5/minute",
    "municipality": "5/minute",
    "my_trip_today": "5/minute",
    "my_trips_today": "5/minute",
    "panchayat_leader_login": "5/minute",
    "panchayat_union": "5/minute",
    "panhayat": "5/minute",
    "permission": "5/minute",
    "permission_assign_api": "5/minute",
    "platform_login": "5/minute",
    "property": "5/minute",
    "public_grievance": "5/minute",
    "recognize": "5/minute",
    "refresh_token": "5/minute",
    "register": "5/minute",
    "scan_bin": "5/minute",
    "staff": "5/minute",
    "staff_access_configuration": "5/minute",
    "staff_access_dashboard": "5/minute",
    "staff_audit": "5/minute",
    "staff_notification": "5/minute",
    "staff_profile": "5/minute",
    "staff_template": "5/minute",
    "staff_user_type": "5/minute",
    "staffcreation": "5/minute",
    "state": "5/minute",
    "state_body_dashboard": "5/minute",
    "state_daily_waste_comparison": "5/minute",
    "state_leader_login": "5/minute",
    "state_monthly_waste_comparison": "5/minute",
    "sub_property": "5/minute",
    "town_panchayat": "5/minute",
    "trip_attendance": "5/minute",
    "trip_history": "5/minute",
    "trip_lifecycle": "5/minute",
    "trip_plan": "5/minute",
    "trip_retrip_request": "5/minute",
    "unassigned_staff_pool": "5/minute",
    "user_charge_rule": "5/minute",
    "user_permissions_api": "5/minute",
    "user_screen": "5/minute",
    "user_screen_action": "5/minute",
    "user_screen_columns_api": "5/minute",
    "user_screen_permission": "5/minute",
    "user_type": "5/minute",
    "validate_bin_qr": "5/minute",
    "vehicle_breakdown": "5/minute",
    "vehicle_creation": "5/minute",
    "vehicle_type_creation": "5/minute",
    "ward": "5/minute",
    "waste_collection": "5/minute",
    "waste_collection_bluetooth": "5/minute",
    "waste_collection_main": "5/minute",
    "waste_collection_sub": "5/minute",
    "waste_type": "5/minute",
}

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'app.authentication.jwt.JWTUserAuthentication',
    ],
    "DEFAULT_PAGINATION_CLASS": None,

    # Global defaults: per-IP for anonymous requests, per-user for
    # authenticated ones, plus each view's own individual scope rate above.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '120/minute',
        **API_THROTTLE_RATES,
    },
}

# -------------------------------------------------------
# CORS SETTINGS
# -------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^http://192\.168\.4\.\d{1,3}(:\d+)?$",
    r"^http://192\.168\.5\.\d{1,3}(:\d+)?$",
    r"^http://192\.168\.3\.\d{1,3}(:\d+)?$",
    r"^http://192\.168\.1\.\d{1,3}(:\d+)?$",
    r"^http://127\.0\.0\.1(:\d+)?$",
    r"^http://125\.17\.238\.158(:\d+)?$",
    r"^http://localhost(:\d+)?$",
    r"^http://192\.168\.4\.58(:\d+)?$",
    r"^http://192\.168\.5\.92(:\d+)?$",
    r"^http://115\.245\.93\.26(:\d+)?$", 
    r"^http://10\.64\.151\.226(:\d+)?$", #dhivya
    r"^http://10\.205\.101\.232(:\d+)?$", #dhivya
    r"^http://10\.244\.208\.158(:\d+)?$",  
    r"^http://10\.183\.250\.158(:\d+)?$",
    r"^http://192\.168\.7\.176(:\d+)?$",
    r"^http://192\.168\.5\.77(:\d+)?$",
    r"^http://192\.168\.5\.20(:\d+)?$",
    r"^http://192\.168\.6\.198(:\d+)?$",
    r"^http://192\.168\.1\.156(:\d+)?$",
    r"^http://192\.168\.3\.120(:\d+)?$",
    r"^http://10\.152\.141\.197(:\d+)?$",
    r"^http://192\.168\.3\.112(:\d+)?$", 
    r"^http://10\.245\.75\.197(:\d+)?$",
    r"^http://10\.255\.70\.197(:\d+)?$", 
    r"^http://192\.168\.6\.238(:\d+)?$",
    r"^http://115\.245\.93\.26(:\d+)?$",
    r"^http://10\.128\.67\.197(:\d+)?$",
    
    "https://aura-haustorial-elayne.ngrok-free.dev",
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# -------------------------------------------------------
# Custom User Model
# -------------------------------------------------------
AUTH_USER_MODEL = "app.User"

MY_API_KEY = os.getenv("MY_API_KEY", "abc123")
ORS_API_KEY = os.getenv("ORS_API_KEY", "")
ORS_OPTIMIZATION_URL = os.getenv(
    "ORS_OPTIMIZATION_URL",
    "https://api.openrouteservice.org/optimization",
)
ORS_DIRECTIONS_URL = os.getenv(
    "ORS_DIRECTIONS_URL",
    "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
)

# -------------------------------------------------------
# Email / SMTP
# -------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@iwms.local')

# -------------------------------------------------------
# Firebase Cloud Messaging (push notifications)
# -------------------------------------------------------
# Path to the Firebase service-account JSON (NOT committed to the repo). Push
# notifications are disabled (safe no-op) until this is set to a real file —
# see app/services/push_notification_service.py.
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")

# OTP settings
OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', 5))
OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', 3))
OTP_RESEND_COOLDOWN_MINUTES = int(os.getenv('OTP_RESEND_COOLDOWN_MINUTES', 2))
OTP_MAX_REQUESTS_PER_WINDOW = int(os.getenv('OTP_MAX_REQUESTS_PER_WINDOW', 3))
OTP_RATE_WINDOW_MINUTES = int(os.getenv('OTP_RATE_WINDOW_MINUTES', 10))

# -------------------------------------------------------
# ATTENDANCE FACE RECOGNITION
# -------------------------------------------------------
# Which engine verifies attendance selfies. Both are fully supported; this is
# the only line that has to change to switch, plus a server restart. The
# register/recognise HTTP contract is identical either way, so the mobile app
# needs no rebuild — it can read the active provider from
# `GET attendance/face-config/`.
#
#   compreface  — the hosted CompreFace API (unchanged, long-standing default)
#   insightface — recognition running inside this server, no external API
#
# Left unset it stays on CompreFace, so deploying this change on its own does
# not silently move anyone onto a different engine.
FACE_RECOGNITION_PROVIDER = os.getenv("FACE_RECOGNITION_PROVIDER", "compreface")

# --- CompreFace (hosted API) ---
# These were hardcoded in the attendance viewsets; they live here now so the
# host can be repointed and the key rotated without a code change.
COMPREFACE_VERIFY_URL = os.getenv(
    "COMPREFACE_VERIFY_URL",
    "http://125.17.238.158:8000/api/v1/verification/verify",
)
COMPREFACE_API_KEY = os.getenv(
    "COMPREFACE_API_KEY", "c4bb2855-e789-45e4-8dcd-903f03e03f2f"
)
COMPREFACE_TIMEOUT = int(os.getenv("COMPREFACE_TIMEOUT", "30"))
# CompreFace's own 0-1 confidence. NOT comparable to the cosine similarity
# InsightFace reports below — each provider carries its own cutoff.
COMPREFACE_MATCH_THRESHOLD = float(os.getenv("COMPREFACE_MATCH_THRESHOLD", "0.95"))

# --- InsightFace (in-process) ---
# Model pack, auto-downloaded to FACE_MODEL_ROOT (~/.insightface) on first
# use. buffalo_s is small and fast; buffalo_l is more accurate but a larger
# download and slower on CPU.
FACE_MODEL_NAME = os.getenv("FACE_MODEL_NAME", "buffalo_s")
FACE_MODEL_ROOT = os.getenv("FACE_MODEL_ROOT", "")
FACE_DET_SIZE = int(os.getenv("FACE_DET_SIZE", "640"))
# Cosine similarity between normalised ArcFace embeddings: genuine matches sit
# around 0.45-0.75, different people around 0.0-0.25. Tune against real punch
# photos before trusting it — and never reuse CompreFace's 0.95 here, which
# would reject every genuine employee.
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.5"))
# Caps the CPU threads one inference may take, so a shift-start burst of
# punches cannot starve the rest of the API on a shared server.
FACE_ONNX_THREADS = int(os.getenv("FACE_ONNX_THREADS", "2"))
FACE_MAX_IMAGE_EDGE = int(os.getenv("FACE_MAX_IMAGE_EDGE", "1280"))
FACE_MIN_DET_SCORE = float(os.getenv("FACE_MIN_DET_SCORE", "0.5"))
FACE_MIN_PIXELS = int(os.getenv("FACE_MIN_PIXELS", "60"))
# Laplacian-variance blur gate. A quality check, not anti-spoofing — a sharp
# photo of a photo passes it. 0 disables.
FACE_MIN_SHARPNESS = float(os.getenv("FACE_MIN_SHARPNESS", "0"))

# -------------------------------------------------------
# JWT CONFIG (import at the end)
# -------------------------------------------------------
from .settings_jwt import *
