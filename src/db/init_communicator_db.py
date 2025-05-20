"""
Database initialization script for the chat Bot.
Run this script to create all required tables for the chat bot.
"""

import os
import asyncio
import logging
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from datetime import datetime
from sqlalchemy.schema import CreateTable
import sys
from loguru import logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database URL from environment - USING THE SAME DATABASE AS THE MAIN BOT
DB_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./allkinds.db")
logger.info(f"Original database URL: {DB_URL[:15]}...")

# Process the database URL - same logic as the main bot
def process_database_url(url):
    # Detect production environment
    is_production = os.environ.get("RAILWAY_ENVIRONMENT") == "production"
    logger.info(f"Production environment: {is_production}")
    
    if not url:
        logger.warning("No database URL provided, falling back to SQLite")
        if is_production:
            logger.error("Production environment requires a valid DATABASE_URL!")
            return None
        return "sqlite+aiosqlite:///./allkinds.db"
    
    # Handle SQLite explicitly
    if url.startswith('sqlite'):
        if is_production:
            logger.error("SQLite cannot be used in production environment!")
            return None
        logger.info("Using SQLite database")
        return url
    
    try:
        # Handle Railway's postgres:// format
        if url.startswith('postgres://') or url.startswith('postgresql://'):
            # For asyncpg, we need to use postgresql+asyncpg://
            if 'asyncpg' not in url:
                if url.startswith('postgres://'):
                    url = url.replace('postgres://', 'postgresql+asyncpg://', 1)
                    logger.info("Converted postgres:// to postgresql+asyncpg://")
                else:
                    url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
                    logger.info("Converted postgresql:// to postgresql+asyncpg://")
            
            logger.info(f"Processed database URL (starts with): {url[:15]}...")
            return url
            
        logger.warning(f"Unrecognized database URL format: {url[:10]}...")
        if is_production:
            logger.error("Production environment requires PostgreSQL!")
            return None
        return url
    except Exception as e:
        logger.error(f"Error processing database URL: {e}")
        if is_production:
            logger.error("Exiting due to database URL processing error in production")
            return None
        logger.info("Falling back to SQLite database")
        return "sqlite+aiosqlite:///./allkinds.db"

# Process the database URL using the same logic as the main bot
DB_URL = process_database_url(DB_URL)
if DB_URL is None:
    logger.critical("Failed to process database URL in production environment!")
    sys.exit(1)
    
logger.info(f"Using database: {DB_URL[:15]}...")

# Create async engine with enhanced parameters
connect_args = {}
if 'postgresql' in DB_URL or 'postgres' in DB_URL:
    connect_args = {
        "timeout": 30,
        "command_timeout": 30,
        "server_settings": {
            "application_name": "allkinds-chat-init"
        },
        "statement_cache_size": 0
    }
    logger.info("Using PostgreSQL connection arguments")

# Create the engine with the same configuration as the main bot
try:
    engine = create_async_engine(
        DB_URL,
        echo=True,
        future=True,
        pool_pre_ping=True,
        pool_recycle=180,
        pool_timeout=45,
        pool_size=10,
        max_overflow=20,
        connect_args=connect_args
    )
    logger.info("Engine created successfully")
except Exception as e:
    logger.critical(f"Failed to create database engine: {e}")
    sys.exit(1)

# Create declarative base
Base = declarative_base()

# Define models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    bio = Column(Text, nullable=True)

class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True)
    initiator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, nullable=False)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

async def setup_chat_db(engine):
    """
    Create tables for the chat bot functionality
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import inspect
    
    try:
        async with AsyncSession(engine) as session:
            inspector = inspect(engine)
            
            # Check if tables exist
            if not await engine.run_sync(lambda sync_conn: inspector.has_table("anonymous_chat_sessions")):
                logger.info("Creating chat_bot-specific tables...")
                # Create tables for chat_bot functionalities
                from sqlalchemy.schema import CreateTable
                
                # Get the table objects from models
                tables = [
                    AnonymousChatSession.__table__,
                    ChatMessage.__table__,
                    BlockedUser.__table__,
                    Chat.__table__,
                ]
                
                # Create tables if they don't exist
                for table in tables:
                    if not await engine.run_sync(lambda sync_conn: inspector.has_table(table.name)):
                        create_expr = CreateTable(table)
                        await session.execute(text(str(create_expr)))
                        logger.info(f"Created table {table.name}")
                
                await session.commit()
                logger.info("All chat_bot tables have been created successfully")
            else:
                logger.info("Chat bot tables already exist")
    
    except Exception as e:
        logger.error(f"Error creating chat_bot tables: {e}")
        raise

async def init_db():
    """Initialize the database by creating all required tables."""
    try:
        logger.info("Starting database initialization process")
        # First, verify database connection
        async with engine.begin() as conn:
            logger.info("Testing database connection...")
            test_result = await conn.execute(text("SELECT 1"))
            result = test_result.scalar()
            logger.info(f"Database connection test result: {result}")
            
            # Create tables if they don't exist
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
        # Create admin user if not exists
        async with AsyncSession(engine) as session:
            # Check if admin user exists
            admin_id = os.environ.get("ADMIN_IDS", "").split(",")[0]
            if admin_id and admin_id.isdigit():
                admin_id = int(admin_id)
                logger.info(f"Checking for admin user with telegram_user_id: {admin_id}")
                query = select(User).where(User.telegram_user_id == admin_id)
                result = await session.execute(query)
                admin_user = result.scalar_one_or_none()
                
                if not admin_user:
                    # Create admin user
                    admin_user = User(
                        telegram_user_id=admin_id,
                        username="admin",
                        first_name="Admin",
                        is_active=True,
                        is_admin=True
                    )
                    session.add(admin_user)
                    await session.commit()
                    logger.info(f"Admin user created with telegram_user_id: {admin_id}")
                else:
                    logger.info(f"Admin user already exists with telegram_user_id: {admin_id}")
            
            # Verify tables contain data
            query = select(User)
            result = await session.execute(query)
            users = result.scalars().all()
            logger.info(f"Found {len(users)} users in the database")
            
            # Log the database URL type for verification
            logger.info(f"Database URL type: {DB_URL.split('://')[0]}")
            
        await setup_chat_db(engine)
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        # In production, we want to fail loudly
        if os.environ.get("RAILWAY_ENVIRONMENT") == "production":
            raise
        return False

if __name__ == "__main__":
    logger.info(f"Initializing database at: {DB_URL}")
    
    try:
        success = asyncio.run(init_db())
        
        if success:
            logger.info("Database initialization completed successfully")
            sys.exit(0)
        else:
            logger.error("Database initialization failed")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled exception during database initialization: {e}")
        sys.exit(1) 