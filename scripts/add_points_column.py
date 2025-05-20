#!/usr/bin/env python3
import asyncio
import sqlite3
import sys
import logging

# Add the root directory to the path
sys.path.append('.')

from src.db.base import SQLALCHEMY_DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Extract the SQLite database path from the URL
DB_PATH = SQLALCHEMY_DATABASE_URL.replace("sqlite+aiosqlite:///", "")

async def add_points_column():
    """Add the points column to the users table."""
    logger.info(f"Connecting to database: {DB_PATH}")
    
    # Use regular SQLite3 for the migration
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if the points column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "points" in column_names:
            logger.info("Points column already exists in users table")
        else:
            # Add the points column with a default value of 0
            logger.info("Adding points column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
            conn.commit()
            logger.info("Points column added successfully")
        
        # Close the connection
        conn.close()
        logger.info("Database connection closed")
        
    except Exception as e:
        logger.error(f"Error adding points column: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(add_points_column()) 