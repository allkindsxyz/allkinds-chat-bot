#!/usr/bin/env python3
"""
Setup and initialization of the Chat Bot's database
"""
import asyncio
import sys
from loguru import logger
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from src.db.base import async_session_maker, get_async_engine
from src.db.models import AnonymousChatSession, ChatMessage, User, Match, BlockedUser, Chat


async def setup_chat_db(engine: AsyncEngine):
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
                logger.info("Creating chat bot-specific tables...")
                # Create tables for chat bot functionalities
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
                logger.info("All chat bot tables have been created successfully")
            else:
                logger.info("Chat bot tables already exist")
    
    except Exception as e:
        logger.error(f"Error creating chat bot tables: {e}")
        raise


async def main():
    """Initialize the chat bot database."""
    try:
        engine = get_async_engine()
        await setup_chat_db(engine)
        logger.info("Chat bot database initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize chat bot database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 