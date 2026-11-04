"""SQLAlchemy engine, session factory, and declarative Base."""
import time
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import OperationalError as SAOperationalError
import psycopg

from backend.app.core.config import settings

logger = logging.getLogger("nodues.database")


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=240,
    connect_args={"connect_timeout": 10},
)


@event.listens_for(engine, "do_connect")
def receive_do_connect(dialect, conn_rec, cargs, cparams):
    """
    Retry connection establishment up to 3 times with exponential backoff on OperationalError.
    Handles Neon serverless compute resuming from idle suspension.
    """
    max_retries = 3
    backoff = 1.0  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            return dialect.connect(*cargs, **cparams)
        except (psycopg.OperationalError, SAOperationalError) as exc:
            if attempt == max_retries:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {exc}")
                raise
            logger.warning(
                f"Database connection attempt {attempt}/{max_retries} failed ({exc}). "
                f"Retrying in {backoff}s (Neon compute may be resuming)..."
            )
            time.sleep(backoff)
            backoff *= 2


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
