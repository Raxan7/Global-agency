import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# CORE SETTINGS
# =============================================================================

SECRET_KEY = config('SECRET_KEY', default='final')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ["*"]

# =============================================================================
# AUTHENTICATION & LOGIN SETTINGS
# =============================================================================

LOGIN_URL = '/employee/login/'
LOGIN_REDIRECT_URL = '/employee/dashboard/'
LOGOUT_REDIRECT_URL = '/employee/login/'

# =============================================================================
# PAYMENT GATEWAY CONFIGURATION
# =============================================================================

CLICKPESA_CLIENT_ID = config('CLICKPESA_CLIENT_ID', default='')
CLICKPESA_API_KEY = config('CLICKPESA_API_KEY', default='')
CLICKPESA_BASE_URL = config('CLICKPESA_BASE_URL', default='https://api.clickpesa.com/third-parties')
CLICKPESA_CHECKSUM = config('CLICKPESA_CHECKSUM', default='')
PAYMENT_GATEWAY = config('PAYMENT_GATEWAY', default='clickpesa')
CURRENCY = config('CURRENCY', default='TZS')

# =============================================================================
# INSTALLED APPS
# =============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'crispy_forms',
    'global_agency',
    'employee',
    'student_portal',
]

# =============================================================================
# MIDDLEWARE (ORDER MATTERS - NO DUPLICATES)
# =============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'globalagency_project.middleware.i18n.LanguageSwitcherMiddleware',
]

ROOT_URLCONF = 'globalagency_project.urls'

# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'globalagency_project.context_processors.language_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'globalagency_project.wsgi.application'

# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': config('DB_NAME'),  # Database name from .env
#         'USER': config('DB_USER'),  # Database username from .env
#         'PASSWORD': config('DB_PASSWORD'),  # Database password from .env
#         'HOST': config('DB_HOST', default='localhost'),  # Database host from .env
#         'PORT': config('DB_PORT', default='3306'),  # Database port from .env
#         'OPTIONS': {
#             'charset': 'utf8mb4',  # Use utf8mb4 for full UTF-8 support including emojis
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1, NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
#             'use_unicode': True,
#         },
#         'TEST': {
#             'CHARSET': 'utf8mb4',
#             'COLLATION': 'utf8mb4_unicode_ci',
#         }
#     }
# }


LANGUAGE_CODE = 'en'
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_L10N = True
USE_TZ = True

from django.utils.translation import gettext_lazy as _

# English is the ONLY supported language
LANGUAGES = [
    ('en', _('English')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# CRITICAL: Language cookie MUST be English and ONLY English
LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_AGE = 31536000
LANGUAGE_COOKIE_PATH = '/'
LANGUAGE_COOKIE_DOMAIN = None
LANGUAGE_COOKIE_SECURE = False if DEBUG else True
LANGUAGE_COOKIE_HTTPONLY = True
LANGUAGE_COOKIE_SAMESITE = 'Lax'

# Force English locale everywhere
LOCALE_NAME = 'en_US'

# Static files configuration
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# =============================================================================
# SESSION & SECURITY SETTINGS
# =============================================================================

SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False if DEBUG else True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = False if DEBUG else True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = True

# =============================================================================
# SECURITY HEADERS
# =============================================================================

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'SAMEORIGIN'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# =============================================================================
# FILE UPLOAD SECURITY
# =============================================================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_PERMISSIONS = 0o644
ALLOWED_UPLOAD_EXTENSIONS = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.gif', '.txt']

# =============================================================================
# CACHING CONFIGURATION
# =============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'africa-western-education',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
            'CULL_FREQUENCY': 4,
        },
        'KEY_PREFIX': 'aweducol',
        'VERSION': 1,
    }
}

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 600
CACHE_MIDDLEWARE_KEY_PREFIX = 'aweducol'
DEFAULT_CACHE_TIMEOUT = 300

# =============================================================================
# TEMPLATE CACHING (Production only)
# =============================================================================

if not DEBUG:
    TEMPLATES[0]['APP_DIRS'] = False
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]

# =============================================================================
# GZIP COMPRESSION
# =============================================================================

GZIP_LEVEL = 9
WHITENOISE_COMPRESS = True
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_ADD_HEADERS_BEFORE = True
WHITENOISE_MANIFEST_STRICT = False

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/django.log',
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': 'logs/security.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO' if DEBUG else 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'student_portal': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'global_agency': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'employee': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# =============================================================================
# ADMIN SETTINGS
# =============================================================================

ADMIN_URL = 'secure-admin-panel/'
ADMIN_ENABLED = True

# =============================================================================
# SEO & ROBOTS SETTINGS
# =============================================================================

ROBOTS_USE_HOST = False
ROBOTS_USE_HTTPS = not DEBUG
ROBOTS_RULES = [
    {'useragent': '*', 'allow': '/'},
    {'useragent': '*', 'disallow': '/admin'},
    {'useragent': '*', 'disallow': '/employee'},
]

SITEMAP_CHANGEFREQ_DEFAULT = 'weekly'
SITEMAP_PRIORITY_DEFAULT = 0.5

GA4_MEASUREMENT_ID = config('GA4_MEASUREMENT_ID', default='')
GOOGLE_SITE_VERIFICATION = config('GOOGLE_SITE_VERIFICATION', default='')
BING_SITE_VERIFICATION = config('BING_SITE_VERIFICATION', default='')

# =============================================================================
# SENTRY ERROR TRACKING (Optional)
# =============================================================================

SENTRY_DSN = config('SENTRY_DSN', default='')

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False
    )

# =============================================================================
# CSRF & TRUSTED ORIGINS
# =============================================================================

CSRF_TRUSTED_ORIGINS = []
if not DEBUG:
    ALLOWED_HOSTS = [
        'africawesterneducation.com',
        'www.africawesterneducation.com',
    ]
    CSRF_TRUSTED_ORIGINS = [
        'https://africawesterneducation.com',
        'https://www.africawesterneducation.com',
    ]