import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# load_dotenv() di atas TIDAK menimpa variabel yang sudah di-export di shell
# (perilaku default) -- itu yang kita mau untuk ALLOWED_HOSTS dkk, supaya
# `export ALLOWED_HOSTS=...,testserver` sebelum menjalankan skrip uji (lihat
# README) tetap bekerja. Tapi khusus kunci yang menentukan infrastruktur mana
# yang dipakai, backend/.env proyek ini harus selalu menang, supaya env var
# nyasar dari project lain di mesin yang sama (mis. DATABASE_URL) tidak
# diam-diam membelokkan Simonda ke database/storage yang salah.
_dotenv_file = dotenv_values(BASE_DIR / ".env")
for _key in ("DATABASE_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
             "R2_BUCKET_NAME", "R2_ENDPOINT_URL"):
    if _key in _dotenv_file:
        os.environ[_key] = _dotenv_file[_key] or ""

SECRET_KEY = os.getenv("SECRET_KEY", "ganti-ini-sebelum-produksi")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "storages",
    "inovasi",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "simonda.urls"
WSGI_APPLICATION = "simonda.wsgi.application"
AUTH_USER_MODEL = "inovasi.User"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

if os.getenv("DATABASE_URL"):
    # Opsional: Postgres terkelola (mis. Neon) lewat satu connection string,
    # kalau suatu saat dipakai lagi. conn_max_age=0 sengaja — banyak Postgres
    # terkelola tier gratis auto-suspend saat idle; koneksi persisten Django
    # yang menahan koneksi lama ke instance yang sudah disuspend adalah
    # sumber error umum ("SSL connection has been closed unexpectedly").
    DATABASES = {"default": dj_database_url.config(
        env="DATABASE_URL", conn_max_age=0, ssl_require=True)}
elif os.getenv("DB_NAME"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }}
else:
    # Basis data utama SANDO (dev maupun produksi/PythonAnywhere). Berkas
    # tunggal di disk -- pastikan db.sqlite3 masuk jadwal backup manual,
    # tidak ada replikasi/point-in-time-recovery otomatis seperti basis data
    # terkelola (lihat README bagian "Deploy gratis").
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Makassar"          # WITA — Rote Ndao
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if os.getenv("R2_BUCKET_NAME"):
    # Cloudflare R2 (kompatibel S3) untuk berkas bukti dukung. Wajib kalau
    # frontend (Cloudflare Pages) dan backend beda domain: berkas.url perlu
    # jadi URL absolut ke R2, bukan path relatif /media/... yang cuma benar
    # kalau frontend-backend satu server. Bucket privat + URL bertanda
    # tangan (perilaku default django-storages) karena bukti dukung berisi
    # dokumen pemerintah, bukan untuk diakses publik.
    AWS_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")  # https://<account_id>.r2.cloudflarestorage.com
    AWS_S3_REGION_NAME = "auto"
    AWS_S3_SIGNATURE_VERSION = "s3v4"     # wajib untuk R2
    AWS_S3_ADDRESSING_STYLE = "path"      # direkomendasikan Cloudflare untuk klien S3
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_EXPIRE = 3600
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [o for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

# SSO dengan Esa Office lewat OpenID Connect (Authorization Code + PKCE); lihat
# inovasi/esa_office.py dan README. Menyala bila ESA_OFFICE_ISSUER diisi; kosong =
# hanya login lokal. Semua alamat harus https (http hanya untuk localhost) dan
# tanpa "#". ESA_OFFICE_CLIENT_SECRET hanya boleh ada di sisi server.
def _env_angka(nama, bawaan, tipe):
    """Setelan numerik dari .env: kosong = bawaan; selain angka > 0 menghentikan
    startup dengan pesan yang menyebut nama variabelnya."""
    mentah = os.getenv(nama, "").strip()
    if not mentah:
        return bawaan
    try:
        nilai = tipe(mentah)
    except ValueError:
        raise ImproperlyConfigured(f"{nama} harus berupa angka (isi sekarang: {mentah!r}).") from None
    if not nilai > 0:
        raise ImproperlyConfigured(f"{nama} harus lebih dari 0 (isi sekarang: {mentah!r}).")
    return nilai


def _env_daftar(nama, bawaan=""):
    return [x.strip() for x in os.getenv(nama, bawaan).split(",") if x.strip()]


ESA_OFFICE_ISSUER = os.getenv("ESA_OFFICE_ISSUER", "").strip()
ESA_OFFICE_CLIENT_ID = os.getenv("ESA_OFFICE_CLIENT_ID", "").strip()
ESA_OFFICE_CLIENT_SECRET = os.getenv("ESA_OFFICE_CLIENT_SECRET", "").strip()
ESA_OFFICE_REDIRECT_URI = os.getenv("ESA_OFFICE_REDIRECT_URI", "").strip()   # https://<backend>/api/auth/esa/callback
ESA_OFFICE_FRONTEND_URL = os.getenv("ESA_OFFICE_FRONTEND_URL", "").strip()   # alamat frontend SANDO
ESA_OFFICE_SCOPE = os.getenv("ESA_OFFICE_SCOPE", "").strip() or "openid profile"
ESA_OFFICE_ALGORITMA = _env_daftar("ESA_OFFICE_ALGORITMA", "RS256,ES256")      # hanya algoritma asimetris
ESA_OFFICE_TIMEOUT = _env_angka("ESA_OFFICE_TIMEOUT", 8.0, float)              # detik
# NIP verifikator/admin SANDO yang dibuat dengan kata sandi lokal dan dipastikan
# orang yang sama dengan pemilik NIP itu di Esa Office; hanya yang terdaftar
# ditautkan otomatis (lihat esa_office.py).
ESA_OFFICE_TAUTKAN_NIP = _env_daftar("ESA_OFFICE_TAUTKAN_NIP")
# 1: OPD diisi otomatis (ESA_ID) bila nama perangkat daerah cocok persis dengan
# tepat satu OPD; 0: hanya OPD yang esa_id-nya sudah diisi admin.
ESA_OFFICE_PETAKAN_OPD_OTOMATIS = os.getenv("ESA_OFFICE_PETAKAN_OPD_OTOMATIS", "1") == "1"
# 1: login dengan kata sandi lokal tetap dibolehkan bagi semua akun; 0: hanya
# administrator (cadangan bila Esa Office mati) selama SSO menyala.
ESA_OFFICE_LOGIN_LOKAL = os.getenv("ESA_OFFICE_LOGIN_LOKAL", "1") == "1"

if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"
    CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_ORIGINS", "").split(",") if o]
