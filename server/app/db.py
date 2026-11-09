"""Database engine and session factory (offline: one MySQL database on the campus server)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .core.config import get_settings


class Base(DeclarativeBase):
    pass


_s = get_settings()
_args = {"check_same_thread": False} if _s.database_url.startswith("sqlite") else {}
engine = create_engine(_s.database_url, pool_pre_ping=True, pool_recycle=1800, connect_args=_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
