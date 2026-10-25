"""SQLAlchemy engine, session factory, and declarative Base."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
