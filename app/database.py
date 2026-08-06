import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


def _get_psycopg2_connection():
    """Create a direct psycopg2 connection with explicit SSL settings."""
    import psycopg2
    # Parse the DATABASE_URL to extract components
    # Format: postgresql://user:pass@host:port/dbname
    url = settings.DATABASE_URL
    # Remove protocol prefix
    rest = url.replace("postgresql://", "").replace("postgres://", "")
    # Split userinfo and hostinfo
    userinfo, hostinfo = rest.split("@")
    user, password = userinfo.split(":")
    host_port, dbname = hostinfo.split("/")
    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 5432

    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        sslmode="require",
        connect_timeout=10,
    )


# Build engine with appropriate connect_args
connect_args = {}
creator = None

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Use a creator function for PostgreSQL to ensure SSL is properly configured
    creator = _get_psycopg2_connection

engine = create_engine(
    settings.DATABASE_URL,
    creator=creator,
    connect_args=connect_args,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called on app startup."""
    Base.metadata.create_all(bind=engine)
