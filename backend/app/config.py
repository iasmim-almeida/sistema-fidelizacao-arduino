import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INSTANCE_DIR = os.path.join(BACKEND_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)
DEFAULT_SQLITE_PATH = os.path.join(INSTANCE_DIR, "fidelizacao.db")


def database_url_from_environment() -> str:
    """Resolve DATABASE_URL ou monta uma URI PostgreSQL a partir das variáveis PG*."""
    database_url = os.getenv("DATABASE_URL", "").strip().strip("'\"")
    if database_url:
        # Render e Neon utilizam postgres://, mas SQLAlchemy 1.4+ exige postgresql:// ou postgresql+psycopg2://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif database_url.startswith("postgresql://") and not database_url.startswith("postgresql+"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return database_url

    host = os.getenv("PGHOST", "").strip()
    database = os.getenv("PGDATABASE", "").strip()
    user = os.getenv("PGUSER", "").strip()
    password = os.getenv("PGPASSWORD", "")
    if not all((host, database, user, password)):
        return f"sqlite:///{DEFAULT_SQLITE_PATH}"

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
    TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")
    INITIAL_SETUP_TOKEN = os.getenv("INITIAL_SETUP_TOKEN", "").strip()
    REQUIRE_INITIAL_SETUP_TOKEN = False
    # Segurança dos Cookies de Sessão
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1")
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    DEBUG = True
    IOT_DEVICE_KEY = os.getenv("IOT_DEVICE_KEY")


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    IOT_DEVICE_KEY = os.getenv("IOT_DEVICE_KEY")
    REQUIRE_INITIAL_SETUP_TOKEN = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() in ("true", "1")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = os.getenv("REMEMBER_COOKIE_SECURE", "True").lower() in ("true", "1")
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Pool otimizado para PostgreSQL Neon (evita desconexões por scale-to-zero / autosuspend)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 30,
        "max_overflow": 10,
    }


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    IOT_DEVICE_KEY = "test-only-device-key-not-for-production"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
