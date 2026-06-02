import logging
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import settings
from sqlalchemy import Column, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func

DeclarativeBase = declarative_base()


class Base(DeclarativeBase):
    __abstract__ = True
    created_at = Column(DateTime, default=func.now(), nullable=False)
    modified_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # let SQLAlchemy handle initialization; keep signature visible to type checkers
        super().__init__(*args, **kwargs)


logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# create session factory to generate new database session
SessionFactory = sessionmaker(
    bind=create_engine(
        settings.database_url,
        pool_size=30,
        max_overflow=20,
        pool_timeout=60,
        pool_recycle=1800,
        pool_pre_ping=True,
    ),
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """Create new database session.

    Yields:
        Database session.
    """

    session = SessionFactory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def open_session() -> Iterator[Session]:
    """Create new database session with context manager.

    Yields:
        Database session.
    """

    return get_db()
