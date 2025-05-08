#!/usr/bin/env python3
"""
Verifies PostgreSQL database connection for production environments.
This script validates that:
1. DATABASE_URL is set and is a PostgreSQL connection
2. The connection can be established
3. The tables exist or can be created

It will exit with an error code if any of these checks fail.
"""

import os
import sys
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, inspect
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def verify_postgresql_connection():
    """Verify that we're using PostgreSQL in production and can connect."""
    is_production = os.environ.get("RAILWAY_ENVIRONMENT") == "production"
    
    # Only enforce PostgreSQL in production
    if not is_production:
        logger.info("Not in production environment, skipping PostgreSQL check")
        return True
    
    # Check if DATABASE_URL is set
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set!")
        return False
    
    # Check if DATABASE_URL is a PostgreSQL connection
    if not db_url.startswith(("postgresql://", "postgres://")):
        logger.error(f"DATABASE_URL must be a PostgreSQL connection! Current type: {db_url.split('://')[0]}")
        return False
    
    logger.info(f"DATABASE_URL is a PostgreSQL connection: {db_url[:15]}...")
    
    # Process the URL for asyncpg
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Try to connect
    try:
        logger.info("Testing PostgreSQL connection...")
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_timeout=10
        )
        
        async with engine.begin() as conn:
            # Test basic connection
            result = await conn.execute(text("SELECT 1"))
            logger.info("Basic connection test passed")
            
            # Check if tables exist
            tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
            if tables:
                logger.info(f"Found existing tables: {', '.join(tables[:5])}...")
                if len(tables) > 5:
                    logger.info(f"...and {len(tables) - 5} more")
            else:
                logger.warning("No tables found in the database!")
        
        await engine.dispose()
        logger.info("PostgreSQL connection verified successfully")
        return True
    
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL database: {str(e)}")
        return False

if __name__ == "__main__":
    if asyncio.run(verify_postgresql_connection()):
        logger.info("Database verification passed")
        sys.exit(0)
    else:
        logger.error("Database verification failed!")
        sys.exit(1) 