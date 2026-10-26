"""Terry Jar — Django sozlamalari. Barcha maxfiy qiymatlar .env dan olinadi (README.md ga qarang)."""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path):
    """Loyiha papkasidagi .env ni o'qiydi (PyCharm/Windows uchun qulay). Muhitda bor qiymat ustun turadi."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip().removeprefix("export ").strip(), val.strip()
        if val[:1] in "\"'" and val[:1] and val.endswith(val[0]) and len(val) > 1:
            val = val[1:-1]
        elif " #" in val:
            val = val.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key, val)


_load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY") or ("dev-insecure-key-change-me" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY topilmadi. Kompyuterda ishlatish uchun: .env.dev.example faylini .env nomi bilan "
        "nusxalang (unda DJANGO_DEBUG=1). Serverda: .env ga DJANGO_SECRET_KEY yozing.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Server ichidagi tekshiruvlar (Docker healthcheck, deploy.sh, o'rnatish skripti) 127.0.0.1 orqali keladi
ALLOWED_HOSTS += [h for h in ("localhost", "127.0.0.1") if h not in ALLOWED_HOSTS]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")
ADMIN_URL = env("DJANGO_ADMIN_URL", "boshqaruv/").strip("/") + "/"
APP_VERSION = env("APP_VERSION", "1.2.0")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "axes",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ForcePasswordChangeMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": dj_database_url.parse(
    env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"), conn_max_age=60, conn_health_checks=True)}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"

REDIS_URL = env("REDIS_URL")
CHANNEL_LAYERS = {"default": (
    {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}
    if REDIS_URL else {"BACKEND": "channels.layers.InMemoryChannelLayer"})}

AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "app"
LOGOUT_REDIRECT_URL = "login"

# Login himoyasi: 5 marta noto'g'ri parol -> 15 daqiqa bloklanadi (login + IP bo'yicha)
AXES_FAILURE_LIMIT = int(env("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = float(env("AXES_COOLOFF_HOURS", "0.25"))
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/locked.html"
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_REAL_IP", "REMOTE_ADDR"]

SESSION_COOKIE_AGE = int(env("SESSION_HOURS", "16")) * 3600  # bir smena + zaxira
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    SECURE_HSTS_SECONDS = int(env("HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
# W008: HTTP->HTTPS yo'naltirishni nginx qiladi; W005/W021: subdomen va preload ro'yxati ataylab yoqilmagan
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021"]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Statik fayllarni Django o'zi beradi (whitenoise) — server qaysi nginx bilan ishlashidan qat'i nazar
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 3600
FRONTEND_HTML = BASE_DIR / "frontend" / "app.html"
DATA_DIR = Path(env("DATA_DIR", str(BASE_DIR / "data")))

DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # zaxiradan tiklash katta paket bo'lishi mumkin

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.request": {"level": "WARNING"}},
}
