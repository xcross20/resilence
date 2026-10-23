import os
from urllib.parse import quote


def _as_psycopg(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def railway_database_url() -> str:
    """Prefer the public TCP proxy when Railway injected it.

    `railway run` on a laptop receives the private hostname too, and that
    hostname is only resolvable inside Railway. The proxy is the laptop path.
    A service running inside Railway with only DATABASE_URL keeps using it.
    """
    domain = os.environ.get("RAILWAY_TCP_PROXY_DOMAIN")
    port = os.environ.get("RAILWAY_TCP_PROXY_PORT")
    user = os.environ.get("PGUSER")
    password = os.environ.get("PGPASSWORD")
    database = os.environ.get("PGDATABASE")
    if domain and port and user and password and database:
        return (
            "postgresql+psycopg://"
            f"{quote(user, safe='')}:{quote(password, safe='')}"
            f"@{domain}:{port}/{quote(database, safe='')}?sslmode=require"
        )
    public = os.environ.get("DATABASE_PUBLIC_URL")
    if public:
        return _as_psycopg(public)
    private = os.environ.get("DATABASE_URL")
    if private:
        return _as_psycopg(private)
    raise RuntimeError("DATABASE_URL is not set")


def create_database_engine(url: str | None = None):
    from sqlalchemy import create_engine

    return create_engine(url or railway_database_url(), connect_args={"connect_timeout": 10}, pool_pre_ping=True)
