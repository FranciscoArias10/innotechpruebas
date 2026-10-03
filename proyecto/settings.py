# -*- coding: utf-8 -*-
"""
Arnes minimo de Django para trabajar aislados del sistema real.

Este archivo NO viaja a sige-ube. Existe solo para que puedan correr
`manage.py test` y `manage.py runserver` sin tener el monolito.

La configuracion de REST_FRAMEWORK y SIMPLE_JWT si es un espejo fiel de la
del sistema real: si algo funciona aqui, funciona alla.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno desde .env si existe
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

SECRET_KEY = os.environ.get('SECRET_KEY', 'arnes-de-desarrollo-no-usar-en-nada-real')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',

    # La app de ustedes. Es lo unico de este proyecto que viaja a sige-ube.
    'app.apps.AppPasantesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'proyecto.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

db_engine = os.environ.get('DB_ENGINE', 'django.db.backends.postgresql')

if 'sqlite3' in db_engine:
    DATABASES = {
        'default': {
            'ENGINE': db_engine,
            'NAME': BASE_DIR / os.environ.get('DB_NAME', 'db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': db_engine,
            'NAME': os.environ.get('DB_NAME', 'uniebec_dev'),
            'USER': os.environ.get('DB_USER', 'fkhalil'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }

LANGUAGE_CODE = 'es-ec'
TIME_ZONE = 'America/Guayaquil'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# ---------------------------------------------------------------------------
# Espejo de la configuracion real (base/my_base.py del sistema)
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 25,

    # Limite de tasa. En el sistema real todavia no existe: es una de las cosas
    # que se van a activar antes de exponer la API. Escriban pensando en que va
    # a estar puesto.
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '120/min',
        'anon': '20/min',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}
