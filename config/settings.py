from pathlib import Path
import os
import pymysql
from dotenv import load_dotenv

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
# REST Framework
# -------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'app.authentication.jwt.JWTUserAuthentication',
    ],
    # Global pagination: limit/offset style with page metadata, 20 items per page
    # "DEFAULT_PAGINATION_CLASS": "app.utils.pagination.LimitOffsetWithPage",
    # "PAGE_SIZE": 20,
    "DEFAULT_PAGINATION_CLASS": None
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
    "https://aura-haustorial-elayne.ngrok-free.dev",
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-permission-cache",
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
# JWT CONFIG (import at the end)
# -------------------------------------------------------
from .settings_jwt import *
