# app/db/init_db.py
from sqlmodel import SQLModel, select
from app.db.session import get_engine
from app.core.security.api_key import create_api_key
from app.models.auth.api_key import Role, APIKey
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def init_db(db_session) -> None:
    """Initialize the database."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

    # Create initial admin API key if enabled
    if settings.API_KEY_AUTH_ENABLED:
        try:
            # Check if any admin key exists
            existing_admin = db_session.exec(
                select(APIKey).where(
                    APIKey.role == Role.ADMIN,
                    APIKey.is_active == True
                )
            ).first()

            if not existing_admin:
                api_key = create_api_key(
                    db_session,
                    name=settings.INITIAL_ADMIN_NAME,
                    role=Role.ADMIN
                )
                logger.info("\n" + "="*60)
                logger.info("INITIAL ADMIN API KEY CREATED")
                logger.info("-"*60)
                logger.info(f"Name: {api_key.name}")
                logger.info(f"Key:  {api_key.key}")
                logger.info(f"Role: {api_key.role}")
                logger.info("-"*60)
                logger.info("IMPORTANT: Save this key - it will not be shown again!")
                logger.info("="*60 + "\n")
            else:
                logger.info("Admin API key already exists, skipping creation")

        except Exception as e:
            logger.error(f"Failed to create initial admin API key: {e}")
            logger.exception("Detailed error:")