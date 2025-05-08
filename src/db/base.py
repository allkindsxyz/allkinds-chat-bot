from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import os
import urllib.parse
from loguru import logger
import re
import sys
import ssl

# Check if we're in Railway
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT') is not None

from src.core.config import get_settings

settings = get_settings()

# Check if we're in production 
IS_PRODUCTION = os.environ.get("RAILWAY_ENVIRONMENT") == "production"

# Prioritize Railway's DATABASE_URL environment variable
ORIGINAL_DB_URL = os.getenv('DATABASE_URL', settings.db_url)
logger.info(f"Original database URL type: {type(ORIGINAL_DB_URL)}")

# Function to safely process database URL
def process_database_url(url):
    if not url:
        # In production, never fall back to SQLite
        if IS_PRODUCTION:
            logger.error("No database URL provided in production environment!")
            logger.error("DATABASE_URL environment variable must be set to a PostgreSQL URL in production.")
            sys.exit(1)
        else:
            logger.warning("No database URL provided, falling back to SQLite")
            return "sqlite+aiosqlite:///./allkinds.db"
    
    logger.info(f"Processing database URL (starts with): {url[:15]}...")
    
    # In production, enforce PostgreSQL
    if IS_PRODUCTION and not (url.startswith('postgres://') or url.startswith('postgresql://')):
        logger.error(f"Invalid database URL in production: {url[:15]}...")
        logger.error("DATABASE_URL must be a PostgreSQL connection in production environment.")
        sys.exit(1)
    
    # Handle SQLite explicitly
    if url.startswith('sqlite'):
        # In production, never use SQLite
        if IS_PRODUCTION:
            logger.error("SQLite database not allowed in production environment!")
            logger.error("DATABASE_URL must be a PostgreSQL connection in production.")
            sys.exit(1)
        else:
            logger.info("Using SQLite database")
            return url

    # Parse the URL to handle parameters safely
    try:
        # Handle Railway's postgres:// format
        if url.startswith('postgres://') or url.startswith('postgresql://'):
            # For asyncpg, we need to use postgresql+asyncpg://
            if 'asyncpg' not in url:
                if url.startswith('postgres://'):
                    url = url.replace('postgres://', 'postgresql+asyncpg://', 1)
                else:
                    url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
            
            # We no longer modify hostnames as they need to remain as provided by Railway
            logger.info(f"Processed database URL (starts with): {url[:15]}...")
            return url
            
        logger.warning(f"Unrecognized database URL format: {url[:10]}...")
        
        # In production, don't allow unrecognized formats
        if IS_PRODUCTION:
            logger.error("Unrecognized database URL format in production!")
            logger.error("DATABASE_URL must be a PostgreSQL connection in production.")
            sys.exit(1)
            
        return url
    except Exception as e:
        logger.error(f"Error processing database URL: {e}")
        
        # In production, don't fall back to SQLite on errors
        if IS_PRODUCTION:
            logger.error("Failed to process database URL in production!")
            logger.error("Please fix the DATABASE_URL environment variable.")
            sys.exit(1)
            
        logger.info("Falling back to SQLite database")
        return "sqlite+aiosqlite:///./allkinds.db"

# Process the database URL
SQLALCHEMY_DATABASE_URL = process_database_url(ORIGINAL_DB_URL)
logger.info(f"Final database URL type: {type(SQLALCHEMY_DATABASE_URL)}")
logger.info(f"Using database driver: {SQLALCHEMY_DATABASE_URL.split('://')[0]}")

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all models."""
    metadata = metadata


# Set connect_args based on database type
connect_args = {}  # Default to empty for SQLite
if 'postgresql' in SQLALCHEMY_DATABASE_URL or 'postgres' in SQLALCHEMY_DATABASE_URL:
    # PostgreSQL specific connect args for asyncpg with more generous timeouts for Railway
    connect_args = {
        "timeout": 60, 
        "command_timeout": 60, 
        "server_settings": {
            "application_name": "allkinds",
            "idle_in_transaction_session_timeout": "60000"
        },
        "statement_cache_size": 0
    }
    
    # Add SSL mode for Railway deployment
    if IS_RAILWAY:
        logger.info("Running on Railway, configuring SSL parameters for global engine")
        connect_args["ssl"] = "prefer"
        logger.info("Configured SSL parameters for global engine: prefer mode")

# Create async engine with enhanced parameters for better connection handling in cloud environments
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,               # Verify connections before using them
    pool_recycle=60,                  # Recycle connections more frequently (1 minute)
    pool_timeout=120,                 # Increased timeout for cloud environments
    pool_size=3,                      # Smaller pool size for better stability
    max_overflow=5,                   # Fewer overflow connections to prevent resource exhaustion
    pool_use_lifo=True,               # Use LIFO for better connection reuse
    connect_args=connect_args         # Database-specific connection arguments
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncSession:
    """Get a database session."""
    async with async_session_factory() as session:
        yield session

def get_engine():
    """Get the SQLAlchemy engine."""
    return engine 

def get_async_engine(*args, **kwargs):
    """Get SQLAlchemy async engine with retry logic."""
    import time
    from sqlalchemy.exc import SQLAlchemyError
    
    # Get database URL from environment with proper error handling
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        database_url = os.environ.get("POSTGRES_URL")
        if database_url:
            logger.info("Using POSTGRES_URL as fallback")
        else:
            logger.critical("No database URL found in environment variables!")
            if IS_RAILWAY:
                # In production, fail fast
                raise ValueError("DATABASE_URL environment variable is required")
            else:
                # In development, use SQLite as a fallback
                logger.warning("Using SQLite as fallback for development in get_async_engine")
                database_url = "sqlite+aiosqlite:///./allkinds.db" # Ensure this fallback is used for logic below
    
    # Force asyncpg driver for PostgreSQL
    if database_url.startswith('postgresql:'): # Check before replace
        database_url = database_url.replace('postgresql:', 'postgresql+asyncpg:')
        logger.info(f"Enforcing asyncpg driver with URL: {database_url[:25]}...")
    elif database_url.startswith('postgres:'): # Check for 'postgres:' as well
        database_url = database_url.replace('postgres:', 'postgresql+asyncpg:')
        logger.info(f"Enforcing asyncpg driver with URL: {database_url[:25]}...")

    # Set connection parameters with sensible timeouts
    connect_args_local = {} # Default to empty for SQLite
    if 'postgresql' in database_url or 'postgres' in database_url: # Check the potentially modified database_url
        connect_args_local = {
            "timeout": 120, 
            "command_timeout": 120, 
            "server_settings": {
                "application_name": "allkinds",
                "idle_in_transaction_session_timeout": "60000"
            },
            "statement_cache_size": 0
        }
        # Add SSL mode for Railway deployment if applicable for this specific database_url
        # IS_RAILWAY check might need to be more nuanced if database_url could be non-Railway postgres
        if IS_RAILWAY and ('postgresql' in database_url or 'postgres' in database_url): # Ensure it's a postgres URL on Railway
            logger.info("Running on Railway, configuring SSL parameters for get_async_engine")
            connect_args_local["ssl"] = "prefer"
            logger.info("Configured SSL parameters for get_async_engine: prefer mode")
    
    # Create engine with retry logic
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            engine = create_async_engine(
                database_url,
                echo=False,
                future=True,
                pool_pre_ping=True,
                pool_recycle=60,
                pool_timeout=120,
                pool_size=3,
                max_overflow=5,
                pool_use_lifo=True,
                connect_args=connect_args_local # Use the locally defined connect_args_local
            )
            logger.info(f"Successfully created database engine on attempt {attempt + 1}")
            return engine
        except SQLAlchemyError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed to establish database connection after {max_retries} attempts: {e}")
                raise

async def init_models(engine):
    """Initialize database models with proper handling for Railway environment."""
    logger.info(f"Initializing database models with engine {engine}...")
    import time
    import asyncio
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy import inspect, text
    
    metadata = Base.metadata
    
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} to initialize database")
            async with engine.begin() as conn:
                # Test connection
                await conn.execute(text("SELECT 1"))
                logger.info("Database connection successful")
                
                # Check if tables exist
                tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
                
                if not tables:
                    logger.info("No tables found. Creating database schema...")
                    await conn.run_sync(metadata.create_all)
                    logger.info("Database schema created.")
                else:
                    logger.info(f"Found existing tables: {tables}")
            
            logger.info("Database models initialized successfully")
            return metadata
            
        except asyncio.exceptions.CancelledError as e:
            # This is a critical issue in Railway - the connection is being cancelled
            logger.error(f"Connection cancelled (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Retry with adjusted timeout
            if attempt < max_retries - 1:
                logger.info(f"Retrying with increased timeout after CancelledError...")
                # If this is a Railway deployment and SSL might be an issue, try a different approach
                if IS_RAILWAY and 'ssl' in str(e).lower():
                    logger.warning("Possible SSL issue detected, trying with different SSL configuration")
                    try:
                        # Create a new engine with alternate SSL settings for next attempt
                        from sqlalchemy.ext.asyncio import create_async_engine
                        # Use a simpler approach for SSL configuration
                        new_connect_args = {
                            "timeout": 120,
                            "command_timeout": 120,
                            "ssl": "allow",  # Try 'allow' mode, which is less strict
                            "server_settings": {
                                "application_name": "allkinds"
                            }
                        }
                        
                        # Create a new engine with the updated settings
                        database_url = str(engine.url)
                        engine = create_async_engine(
                            database_url,
                            connect_args=new_connect_args,
                            pool_recycle=120,
                            pool_timeout=60,
                            pool_size=5,
                            max_overflow=10,
                            pool_use_lifo=True
                        )
                    except Exception as ssl_config_error:
                        logger.error(f"Failed to reconfigure engine with SSL settings: {ssl_config_error}")
                
                if IS_RAILWAY:
                    logger.warning("Attempting to continue despite cancellation in Railway...")
                    try:
                        # Try a direct database connection as a last resort
                        import asyncpg
                        db_url = os.environ.get("DATABASE_URL", "")
                        if db_url:
                            logger.info("Attempting direct asyncpg connection as last resort")
                            conn = await asyncpg.connect(
                                db_url, 
                                ssl="allow",  # Use 'allow' for the last resort connection
                                timeout=60
                            )
                            await conn.close()
                            logger.info("Direct connection succeeded, service should continue")
                            return metadata
                    except Exception as direct_e:
                        logger.critical(f"Final direct connection attempt failed: {direct_e}")
                
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                if IS_PRODUCTION:
                    logger.error("Database initialization failed in production environment!")
                    raise  # Re-raise in production
                else:
                    logger.warning("Continuing without proper database initialization in development environment")
                    return metadata
                    
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying database initialization in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Database initialization failed after {max_retries} attempts due to SQLAlchemy error: {e}")
                if IS_PRODUCTION:
                    logger.error("Database initialization failed in production environment!")
                    raise  # Re-raise in production
                else:
                    logger.warning("Continuing without proper database initialization in development environment")
                    return metadata
                    
        except Exception as e:
            logger.error(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying database initialization in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Database initialization failed after {max_retries} attempts due to: {e}")
                if IS_PRODUCTION:
                    logger.error("Database initialization failed in production environment!")
                    raise  # Re-raise in production
                else:
                    logger.warning("Continuing without proper database initialization in development environment")
                    return metadata
