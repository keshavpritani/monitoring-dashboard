"""
Django settings for status_service project.

Generated by 'django-admin startproject' using Django 2.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import boto3, json

locally = True

def get_secret(secret_arn):
    global locally
    if locally:
        connection_json = {
            'host': '127.0.0.1',
            'port': '5432',
            'username': 'keshav',
            'password': 'root'
            }
        return connection_json
    region_name = "us-east-1"
    session = boto3.session.Session() # type: ignore
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    print("secret_arn: ", secret_arn)
    get_secret_value_response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(get_secret_value_response['SecretString'])

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'ht$os!c)sjb#_nxg*difh35g7(w1#(92)ka-xle_o!n-z%0gjt'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'status',
    'infra',
    'admin_console',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend'
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}


ROOT_URLCONF = 'status_service.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'status_service.wsgi.application'

SITE_ID = 2

# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

devops_db = get_secret("arn:aws:secretsmanager:us-east-1:348221620929:secret:staging-devops-HjsfNA")
vpn2_db = get_secret("arn:aws:secretsmanager:us-east-1:348221620929:secret:staging-vpn2-writer-oIIufw")
kyc_db = get_secret("arn:aws:secretsmanager:us-east-1:348221620929:secret:staging-kyc-writer-zHWMwt")
reports_db = get_secret("arn:aws:secretsmanager:us-east-1:348221620929:secret:staging-reports-writer-keQnQf")

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': devops_db['username'],
        'PASSWORD': devops_db['password'],
        'HOST': devops_db['host'],
        'PORT': devops_db['port'],
    },
    'queue': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': kyc_db['username'],
        'PASSWORD': kyc_db['password'],
        'HOST': kyc_db['host'],
        'PORT': kyc_db['port'],
    },
    'vpn2': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': vpn2_db['username'],
        'PASSWORD': vpn2_db['password'],
        'HOST': vpn2_db['host'],
        'PORT': vpn2_db['port'],
    },
    'kpm': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': kyc_db['username'],
        'PASSWORD': kyc_db['password'],
        'HOST': kyc_db['host'],
        'PORT': kyc_db['port'],
    },
    'kyc': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': kyc_db['username'],
        'PASSWORD': kyc_db['password'],
        'HOST': kyc_db['host'],
        'PORT': kyc_db['port'],
    },
    'kristaldata': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': vpn2_db['username'],
        'PASSWORD': vpn2_db['password'],
        'HOST': vpn2_db['host'],
        'PORT': vpn2_db['port'],
    },
    'funds': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': kyc_db['username'],
        'PASSWORD': kyc_db['password'],
        'HOST': kyc_db['host'],
        'PORT': kyc_db['port'],
    },
    'reports': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': reports_db['username'],
        'PASSWORD': reports_db['password'],
        'HOST': reports_db['host'],
        'PORT': reports_db['port'],
    },
    'vpn2-writer': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': vpn2_db['username'],
        'PASSWORD': vpn2_db['password'],
        'HOST': vpn2_db['host'],
        'PORT': vpn2_db['port'],
    },
}

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/static/'

# Email
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'email-smtp.ap-southeast-1.amazonaws.com'
# EMAIT_PORT = 465
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = ''
# EMAIL_HOST_PASSWORD = ''