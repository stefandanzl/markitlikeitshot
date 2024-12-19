from sqlmodel import create_engine, Session
from app.core.config import settings
from functools import lru_cache

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

def get_db():
    """Get database session."""
    engine = get_engine()
    with Session(engine) as session:
        yield session