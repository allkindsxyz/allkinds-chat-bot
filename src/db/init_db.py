from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import inspect, text
import asyncio
import time

# Import models at module level to register them with Base metadata
from src.db.base import Base, SQLALCHEMY_DATABASE_URL
# Import models at module level to make them available to SQLAlchemy metadata
import src.db.models  # This registers all models with Base


async def init_db(max_retries=5, retry_delay=2):
    """Initialize the database and create tables if they don't exist.
    
    Args:
        max_retries: Maximum number of connection retries
        retry_delay: Delay between retries in seconds
    """
    logger.info(f"Initializing database with URL type: {SQLALCHEMY_DATABASE_URL.split('://')[0]}")
    
    # Set connect_args based on database type
    connect_args = {}
    if 'postgresql' in SQLALCHEMY_DATABASE_URL or 'postgres' in SQLALCHEMY_DATABASE_URL:
        connect_args = {
            "timeout": 30,
            "command_timeout": 30,
            "server_settings": {
                "application_name": "allkinds_init"
            },
            "statement_cache_size": 0
        }
    
    # Create engine with improved connection parameters for Railway
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL, 
        echo=True,
        pool_pre_ping=True,
        pool_recycle=180,                 # Recycle connections more frequently (3 minutes),              # Recycle connections more frequently (3 minutes)
        pool_timeout=45,                  # Increased timeout for cloud environments,               # Increased pool timeout for cloud environments
        pool_size=10,                     # Increased pool size for better concurrency,                   # Keep limited pool size for initialization
        max_overflow=20,           # Allow more overflow connections for spikes,               # Allow some overflow
        connect_args=connect_args
    )
    
    # Try to connect with retries
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                # Test connection using sqlalchemy.text()
                await conn.execute(text("SELECT 1"))
                logger.info("Database connection successful")
                
                # Check if tables exist using run_sync
                tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
                
                if not tables:
                    logger.info("No tables found. Creating database schema...")
                    await conn.run_sync(Base.metadata.create_all)
                    logger.info("Database schema created.")
                else:
                    logger.info(f"Found existing tables: {tables}")
                
                # If we got here, we're done
                break
        except Exception as e:
            logger.error(f"Database connection error (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                delay = retry_delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                # Don't raise here - let the app continue and try to work with what it has
                # It might be a temporary network issue that resolves itself
    
    await engine.dispose()
    logger.info("Database initialization complete.")

# TODO: Integrate Alembic for proper migrations 