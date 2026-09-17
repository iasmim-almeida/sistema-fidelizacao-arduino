import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


def database_url_from_environment() -> str:
    """Resolve DATABASE_URL or monta uma URI PostgreSQL a partir das variáveis PG*."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url.strip("'\"")

    host = os.getenv("PGHOST", "").strip()
    database = os.getenv("PGDATABASE", "").strip()
    user = os.getenv("PGUSER", "").strip()
    password = os.getenv("PGPASSWORD", "")
    if not all((host, database, user, password)):
        return "sqlite:///fidelizacao.db"

    sslmode = os.getenv("PGSSLMODE", "require").strip()
    channel_binding = os.getenv("PGCHANNELBINDING", "require").strip()
    return (
        f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}/{database}?sslmode={quote_plus(sslmode)}"
        f"&channel_binding={quote_plus(channel_binding)}"
    )


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = database_url_from_environment()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    PONTOS_POR_REAL = int(os.getenv("PONTOS_POR_REAL", "1"))
    TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")
    # Segurança dos Cookies de Sessão
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1")
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    DEBUG = True
    IOT_DEVICE_KEY = os.getenv("IOT_DEVICE_KEY", "fideliza-iot-key-padrao")


class ProductionConfig(Config):
    DEBUG = False
    _secret = os.getenv("SECRET_KEY")
    if not _secret or _secret in ("dev-secret-key", "troque-por-uma-chave-longa-e-aleatoria"):
        import secrets
        import warnings
        SECRET_KEY = secrets.token_hex(32)
        warnings.warn(
            "ALERTA DE SEGURANÇA: SECRET_KEY ausente ou insegura em produção! "
            "Uma chave criptográfica forte temporária foi gerada dinamicamente.",
            RuntimeWarning,
            stacklevel=2,
        )
    else:
        SECRET_KEY = _secret

    IOT_DEVICE_KEY = os.getenv("IOT_DEVICE_KEY")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1")


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    IOT_DEVICE_KEY = "fideliza-iot-key-padrao"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
