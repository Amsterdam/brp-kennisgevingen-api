from pathlib import Path

import environ
from pythonjsonlogger import json

env = environ.Env()
_USE_SECRET_STORE = Path("/mnt/secrets-store").exists()

# -- Environment

SRC_DIR = Path(__file__).parents[1]

CLOUD_ENV = env.str("CLOUD_ENV", "default").lower()
DEBUG = env.bool("DJANGO_DEBUG", default=(CLOUD_ENV == "default"))

# Whitenoise needs a place to store static files and their gzipped versions.
STATIC_ROOT = env.str("STATIC_ROOT", str(SRC_DIR.parent / "web/static"))
STATIC_URL = env.str("STATIC_URL", "/static/")

# -- Security

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str("SECRET_KEY", "insecure")

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", not DEBUG)

INTERNAL_IPS = ("127.0.0.1",)

TIME_ZONE = "Europe/Amsterdam"

# -- Application definition

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "brp_kennisgevingen",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "brp_kennisgevingen.api.middleware.APIVersionMiddleware",
    "authorization_django.authorization_middleware",
]

if DEBUG:
    INSTALLED_APPS += [
        "debug_toolbar",
        "django_extensions",
    ]
    MIDDLEWARE.insert(1, "debug_toolbar.middleware.DebugToolbarMiddleware")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "brp_kennisgevingen.urls"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(SRC_DIR / "templates")],
        "OPTIONS": {
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

if not DEBUG:
    # Keep templates in memory
    TEMPLATES[0]["OPTIONS"]["loaders"] = [
        ("django.template.loaders.cached.Loader", TEMPLATES[0]["OPTIONS"]["loaders"]),
    ]

WSGI_APPLICATION = "brp_kennisgevingen.wsgi.application"

# -- Services

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

CACHES = {"default": env.cache_url(default="locmemcache://")}

if _USE_SECRET_STORE or CLOUD_ENV.startswith("azure"):
    # On Azure, passwords are NOT passed via environment variables,
    # because the container environment can be inspected, and those vars export to subprocesses.
    pgpassword = Path(env.str("AZ_PG_TOKEN_PATH")).read_text()

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.str("PGDATABASE"),
            "USER": env.str("PGUSER"),
            "PASSWORD": pgpassword,
            "HOST": env.str("PGHOST"),
            "PORT": env.str("PGPORT"),
            "DISABLE_SERVER_SIDE_CURSORS": True,
            "OPTIONS": {
                "sslmode": env.str("PGSSLMODE", default="require"),
            },
        }
    }
    DATABASE_SET_ROLE = True
else:
    # Regular development
    DATABASES = {
        "default": env.db_url(
            "DATABASE_URL",
            default="postgres://dataservices:insecure@localhost:5416/brp_kennisgevingen",
            engine="django.db.backends.postgresql",
        ),
    }
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"].setdefault("DISABLE_SERVER_SIDE_CURSORS", True)
    DATABASE_SET_ROLE = env.bool("DATABASE_SET_ROLE", False)

DATABASES["default"]["OPTIONS"]["application_name"] = "BRP-KENNISGEVINGEN-API"

locals().update(env.email_url(default="smtp://"))

# -- Logging


class CustomJsonFormatter(json.JsonFormatter):
    def __init__(self, *args, **kwargs):
        # Make sure some 'extra' fields are not included:
        super().__init__(*args, **kwargs)
        self._skip_fields.update({"request": "request", "taskName": "taskName"})

    def add_fields(self, log_record: dict, record, message_dict: dict):
        # The 'rename_fields' logic fails when fields are missing, this is easier:
        super().add_fields(log_record, record, message_dict)
        # An in-place reordering, sotime/level appear first (easier for docker log scrolling)
        ordered_dict = {
            "time": log_record.pop("asctime", record.asctime),
            "level": log_record.pop("levelname", record.levelname),
            **log_record,
        }
        log_record.clear()
        log_record.update(ordered_dict)


_json_log_formatter = {
    "()": CustomJsonFormatter,
    "format": "%(asctime)s $(levelname)s %(name)s %(message)s",  # parsed as a fields list.
}

DJANGO_LOG_LEVEL = env.str("DJANGO_LOG_LEVEL", "INFO")
LOG_LEVEL = env.str("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
AUDIT_LOG_LEVEL = env.str("AUDIT_LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "json": _json_log_formatter,
        "audit_json": {
            **_json_log_formatter,
            "static_fields": {"audit": True},
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "console_print": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        },
        "audit_console": {
            # For azure, this is replaced below.
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "audit_json",
        },
    },
    "root": {
        "level": DJANGO_LOG_LEVEL,
        "handlers": ["console"],
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": DJANGO_LOG_LEVEL, "propagate": False},
        "django.utils.autoreload": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "brp_kennisgevingen": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "brp_kennisgevingen.audit": {
            "handlers": ["audit_console"],
            "level": AUDIT_LOG_LEVEL,
            "propagate": False,
        },
        "authorization_django": {
            "handlers": ["audit_console"],
            "level": AUDIT_LOG_LEVEL,
            "propagate": False,
        },
        "apikeyclient": {"handlers": ["console"], "propagate": False},
    },
}

if DEBUG:
    # Print tracebacks without JSON formatting.
    LOGGING["loggers"]["django.request"] = {
        "handlers": ["console_print"],
        "level": "ERROR",
        "propagate": False,
    }

# -- Azure specific settings
if CLOUD_ENV.startswith("azure"):
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes

    # Microsoft recommended abbreviation for Application Insights is `APPI`
    AZURE_APPI_CONNECTION_STRING = env.str("AZURE_APPI_CONNECTION_STRING")
    AZURE_APPI_AUDIT_CONNECTION_STRING = env.str("AZURE_APPI_AUDIT_CONNECTION_STRING", None)

    # Configure OpenTelemetry to use Azure Monitor with the specified connection string
    if AZURE_APPI_CONNECTION_STRING is not None:
        configure_azure_monitor(
            connection_string=AZURE_APPI_CONNECTION_STRING,
            logger_name="root",
            instrumentation_options={
                "azure_sdk": {"enabled": False},
                "django": {"enabled": False},  # Manually done
                "fastapi": {"enabled": False},
                "flask": {"enabled": False},
                "psycopg2": {"enabled": False},  # Manually done
                "requests": {"enabled": True},
                "urllib": {"enabled": True},
                "urllib3": {"enabled": True},
            },
            resource=Resource.create({ResourceAttributes.SERVICE_NAME: "brp-kennisgevingen-api"}),
        )
        print("OpenTelemetry has been enabled")

        def response_hook(span, request, response):
            if (
                span.is_recording()
                and hasattr(request, "get_token_claims")
                and (email := request.get_token_claims.get("email", request.get_token_subject))
            ):
                span.set_attribute("user.AuthenticatedId", email)

        DjangoInstrumentor().instrument(response_hook=response_hook)
        print("Django instrumentor enabled")

        # Psycopg2Instrumentor().instrument(enable_commenter=True, commenter_options={})
        # print("Psycopg instrumentor enabled")

    if AZURE_APPI_AUDIT_CONNECTION_STRING is not None:
        # Configure audit logging to an extra log
        from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        audit_logger_provider = LoggerProvider()
        audit_logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                AzureMonitorLogExporter(connection_string=AZURE_APPI_AUDIT_CONNECTION_STRING)
            )
        )

        # Attach LoggingHandler to namespaced logger
        # same as: handler = LoggingHandler(logger_provider=audit_logger_provider)
        LOGGING["handlers"]["audit_console"] = {
            "level": "DEBUG",
            "class": "opentelemetry.sdk._logs.LoggingHandler",
            "logger_provider": audit_logger_provider,
            "formatter": "audit_json",
        }
        for logger_name, logger_details in LOGGING["loggers"].items():
            if "audit_console" in logger_details["handlers"]:
                LOGGING["loggers"][logger_name]["handlers"] = ["audit_console", "console"]
        print("Audit logging has been enabled")


# -- Third party app settings

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = env.list(
    "CORS_ALLOWED_ORIGIN_REGEXES",
    default=(
        [
            r"^http://localhost(?::\d+)?",
            r"^http://127.0.0.1(?::\d+)?",
        ]
        if DEBUG
        else []
    ),
)

HEALTH_CHECKS = {
    "app": lambda request: True,
    # "database": "django_healthchecks.contrib.check_database",
    # 'cache': 'django_healthchecks.contrib.check_cache_default',
    # 'ip': 'django_healthchecks.contrib.check_remote_addr',
}
HEALTH_CHECKS_ERROR_CODE = 503

REST_FRAMEWORK = dict(
    DEFAULT_RENDERER_CLASSES=[
        # Removed HTML rendering, Give pure application/problem+json responses instead.
        # The HTML rendering is not needed and conflicts with the exception_handler code.
        "rest_framework.renderers.JSONRenderer",
    ],
    EXCEPTION_HANDLER="brp_kennisgevingen.views.exception_handler",
    UNAUTHENTICATED_USER=None,  # Avoid importing django.contrib.auth.models
    UNAUTHENTICATED_TOKEN=None,
    URL_FORMAT_OVERRIDE="_format",  # use ?_format=.. instead of ?format=..
    DEFAULT_SCHEMA_CLASS="brp_kennisgevingen.openapi.schema.AutoSchema",
    DEFAULT_AUTHENTICATION_CLASSES=[],
)

SPECTACULAR_SETTINGS = {
    "TITLE": "BRP Kennisgevingen API",
    "DESCRIPTION": "BRP Kennisgevingen API",
    "CONTACT": {"email": "datapunt@amsterdam.nl"},
    "VERSION": "1.0.0",
    "LICENSE": {
        "name": "European Union Public License, version 1.2 (EUPL-1.2)",
        "url": "https://eupl.eu/1.2/nl/",
    },
    "SCHEMA_PATH_PREFIX_INSERT": env.str("SCHEMA_PATH_PREFIX_INSERT", None),
    "AUTHENTICATION_WHITELIST": None,
    "PREPROCESSING_HOOKS": [
        "brp_kennisgevingen.openapi.preprocessors.preprocessing_filter_spec",
    ],
    "TAGS": [
        {"name": "Manage subscriptions"},
        {"name": "List updates"},
    ],
}

# -- Amsterdam oauth settings

DATAPUNT_AUTHZ = {
    # To verify JWT tokens, either the PUB_JWKS or a OAUTH_JWKS_URL needs to be set.
    "JWKS": env.str("PUB_JWKS", None),
    "JWKS_URL": env.str("OAUTH_JWKS_URL", None),
    "CHECK_CLAIMS": env.dict("OAUTH_CHECK_CLAIMS", default={}),
    # "ALWAYS_OK": True if DEBUG else False,
    "ALWAYS_OK": False,
    "MIN_INTERVAL_KEYSET_UPDATE": 30 * 60,  # 30 minutes
}
