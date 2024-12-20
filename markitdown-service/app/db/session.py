from sqlmodel import create_engine, Session
from app.core.config import settings
from functools import lru_cache
from contextlib import contextmanager
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

@lru_cache()
def get_engine():
    """Create cached SQLModel engine."""
    return create_engine(
        settings.DATABASE_URL,
        connect_args=settings.DATABASE_CONNECT_ARGS,
        pool_size=settings.DATABASE_POOL_SIZE,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        echo=settings.DATABASE_ECHO,
    )

@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    
    Usage:
        with get_db_session() as session:
            result = session.query(...)
            # Session will automatically commit on success
            # or rollback on exception
    """
    engine = get_engine()
    session = Session(engine)
    try:
        yield session
        session.commit()
    except HTTPException:
        # Don't log HTTPExceptions as errors - they're expected
        session.rollback()
        raise
    except Exception as e:
        logger.exception("Database session error, rolling back transaction")
        session.rollback()
        raise
    finally:
        logger.debug("Closing database session")
        session.close()

def get_db():
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @router.get("/")
        async def endpoint(db: Session = Depends(get_db)):
            result = db.query(...)
    """
    with get_db_session() as session:
        yield session

__all__ = ["get_engine", "get_db", "get_db_session"]