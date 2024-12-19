from sqlmodel import SQLModel, select
from app.db.session import get_engine, get_db_session
from app.core.security.api_key import create_api_key
from app.models.auth.api_key import Role, APIKey
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def init_db(db_session) -> None:
    """Initialize the database."""
    engine = get_engine()
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")

    # Create initial admin API key if enabled
    if settings.API_KEY_AUTH_ENABLED:
        try:
            logger.info("Checking for existing admin API keys...")
            # Check if any admin key exists
            existing_admin = db_session.exec(
                select(APIKey).where(
                    APIKey.role == Role.ADMIN,
                    APIKey.is_active == True
                )
            ).first()

            if not existing_admin:
                logger.info("No admin key found. Creating initial admin API key...")
                api_key = create_api_key(
                    db_session,
                    name=settings.INITIAL_ADMIN_NAME,
                    role=Role.ADMIN
                )
                
                # Print the admin key box directly to console
                box = f"""
============================================================
INITIAL ADMIN API KEY CREATED
------------------------------------------------------------
Name: {api_key.name}
Key:  {api_key.key}
Role: {api_key.role}
------------------------------------------------------------
IMPORTANT: Save this key - it will not be shown again!
============================================================
"""
                print(box)
                
                logger.info("Initial admin API key created successfully")
            else:
                logger.info(f"Found existing admin key for: {existing_admin.name}")
                logger.info("Skipping initial admin key creation")

        except Exception as e:
            logger.error(f"Failed to create initial admin API key: {e}")
            logger.exception("Detailed error:")
            raise

    logger.info("Database initialization completed successfully")

def ensure_db_initialized():
    """
    Ensure database is initialized. This is a convenience function
    that can be called during application startup.
    """
    try:
        with get_db_session() as db:
            init_db(db)
    except Exception as e:
        logger.error("Failed to initialize database")
        logger.exception(e)
        raise

__all__ = ["init_db", "ensure_db_initialized"]