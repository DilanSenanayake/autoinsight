"""
Django settings for Vehicle Evaluator project.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-change-in-production-vehicle-evaluator'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

_default_hosts = 'localhost,127.0.0.1,.vercel.app'
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', _default_hosts).split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'evaluator',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vehicle_evaluator.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vehicle_evaluator.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'evaluator' / 'static'] if (BASE_DIR / 'evaluator' / 'static').exists() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Groq API - set GROQ_API_KEY in environment or .env
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# Session storage for evaluation results (optional, for re-filtering)
# On Vercel we use signed cookies so no database is required (ephemeral filesystem).
if os.environ.get('VERCEL'):
    SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
else:
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = os.environ.get('VERCEL') == '1'

# Logging configuration for vehicle scraper and ranking
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': 'INFO',
        },
    },
    'loggers': {
        'evaluator.scraper': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'evaluator.ranking': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'evaluator.views': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Only add file handler for local development (not on Vercel)
if not os.environ.get('VERCEL'):
    _logs_dir = BASE_DIR / 'logs'
    _logs_dir.mkdir(exist_ok=True)
    
    file_handler = {
        'class': 'logging.FileHandler',
        'filename': _logs_dir / 'scraper.log',
        'formatter': 'verbose',
        'level': 'INFO',
    }
    LOGGING['handlers']['file'] = file_handler
    
    # Add file handler to all loggers for local development
    for logger_name in ['evaluator.scraper', 'evaluator.ranking', 'evaluator.views']:
        LOGGING['loggers'][logger_name]['handlers'].append('file')
