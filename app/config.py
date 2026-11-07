import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024 + 64 * 1024
    WTF_CSRF_TIME_LIMIT = 3600
    DB_HOST = os.environ.get("DB_HOST", "postgres")
    DB_PORT = int(os.environ.get("DB_PORT", "5432"))
    DB_NAME = os.environ.get("DB_NAME", "medicare")
    DB_USER = os.environ.get("DB_USER", "medicare")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_SSLMODE = os.environ.get("DB_SSLMODE", "prefer")
    DB_SSLROOTCERT = os.environ.get("DB_SSLROOTCERT")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    S3_BUCKET = os.environ.get("S3_BUCKET", "medicare-documents")
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL") or None
    S3_PUBLIC_ENDPOINT_URL = os.environ.get("S3_PUBLIC_ENDPOINT_URL") or None
    AWS_REGION = os.environ.get("AWS_REGION", "eu-west-3")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")