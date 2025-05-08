import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime

import aiosqlite

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database file path - get the absolute path to the project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = os.path.join(PROJECT_ROOT, "allkinds.db")


async def create_chats_table():
    """Create the chats table if it doesn't exist."""
    logger.info(f"Starting migration: Creating chats table using DB at {DB_PATH}")
    
    try:
        # Connect to the database
        async with aiosqlite.connect(DB_PATH) as db:
            # Get the cursor
            cursor = await db.cursor()
            
            # Check if the table exists
            await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chats'")
            table_exists = await cursor.fetchone()
            
            if table_exists:
                logger.info("chats table already exists in the database")
                return
            
            # Create the chats table
            logger.info("Creating chats table")
            await cursor.execute("""
                CREATE TABLE chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    initiator_id INTEGER NOT NULL REFERENCES users(id),
                    recipient_id INTEGER NOT NULL REFERENCES users(id),
                    group_id INTEGER NOT NULL REFERENCES groups(id),
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (initiator_id, recipient_id, group_id)
                )
            """)
            
            # Commit the changes
            await db.commit()
            logger.info("chats table created successfully")
            
    except Exception as e:
        logger.error(f"Error creating chats table: {e}")
        raise


if __name__ == "__main__":
    # Run the migration
    asyncio.run(create_chats_table()) 