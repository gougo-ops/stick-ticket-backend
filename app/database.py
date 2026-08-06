from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

# Build connect_args based on database type
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# For PostgreSQL, prefer DATABASE_ARGS env var for flexibility
# Internal Railway PG doesn't need sslmode
if settings.DATABASE_URL.startswith("postgresql"):
    if "railway.internal" in settings.DATABASE_URL:
        connect_args = {"connect_timeout": 10}
    else:
        connect_args = {"sslmode": "require", "connect_timeout": 10}

engine = create_engine(
    settings.DATABASE_URL,
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
