from sqlmodel import SQLModel, select
from app.db.session import get_engine, get_db_session
from app.core.security.api_key import create_api_key
from app.models.auth.api_key import Role, APIKey
from app.models.auth.user import User, UserStatus
from app.core.security.user import create_user
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def init_db(db_session) -> None:
    """Initialize the database."""
    engine = get_engine()
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine, checkfirst=True)
    logger.info("Database tables created successfully")

    # Create initial admin user and API key if enabled
    if settings.API_KEY_AUTH_ENABLED:
        try:
            logger.info("Checking for existing admin user...")
            # Check if admin user exists
            existing_admin = db_session.exec(
                select(User).where(
                    User.email == settings.INITIAL_ADMIN_EMAIL
                )
            ).first()

            admin_user = None
            if not existing_admin:
                logger.info("No admin user found. Creating initial admin user...")
                admin_user = create_user(
                    db=db_session,
                    name=settings.INITIAL_ADMIN_NAME,
                    email=settings.INITIAL_ADMIN_EMAIL,
                    status=UserStatus.ACTIVE
                )
                logger.info(f"Created admin user: {admin_user.name}")
            else:
                admin_user = existing_admin
                logger.info(f"Found existing admin user: {admin_user.name}")

            # Check for admin API key
            logger.info("Checking for existing admin API keys...")
            existing_admin_key = db_session.exec(
                select(APIKey).where(
                    APIKey.role == Role.ADMIN,
                    APIKey.user_id == admin_user.id,
                    APIKey.is_active == True
                )
            ).first()

            if not existing_admin_key:
                logger.info("No admin key found. Creating initial admin API key...")
                api_key = create_api_key(
                    db=db_session,
                    name=f"{settings.INITIAL_ADMIN_NAME}'s Admin Key",
                    role=Role.ADMIN,
                    user_id=admin_user.id
                )
                
                # Log the admin key box using logger
                box = f"""
============================================================
INITIAL ADMIN SETUP COMPLETE
------------------------------------------------------------
Admin User:
  Name:  {admin_user.name}
  Email: {admin_user.email}
  ID:    {admin_user.id}

Admin API Key:
  Name:  {api_key.name}
  Key:   {api_key.key}
  Role:  {api_key.role.value}
------------------------------------------------------------
IMPORTANT: Save this key - it will not be shown again!
============================================================"""
                logger.info("\n" + box)
                
                logger.info("Initial admin API key created successfully")
            else:
                logger.info(f"Found existing admin key for: {existing_admin_key.name}")
                logger.info("Skipping initial admin key creation")

        except Exception as e:
            logger.error(f"Failed to create initial admin user/key: {e}")
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