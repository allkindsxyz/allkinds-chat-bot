#!/usr/bin/env python3
import asyncio
import sys
import logging
from sqlalchemy import select, func, update

# Add the root directory to the path
sys.path.append('.')

from src.db.base import Base, SQLALCHEMY_DATABASE_URL, async_session_factory
from src.db.models import User, Question, Answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def update_points():
    """Update user points based on their contributions."""
    # Use the async_session_factory directly
    logger.info("Starting points update...")
    
    # Create a session using the factory
    async with async_session_factory() as session:
        try:
            # First, get all users
            users_query = select(User)
            result = await session.execute(users_query)
            users = result.scalars().all()
            
            logger.info(f"Found {len(users)} users to update points for")
            
            # Process each user
            for user in users:
                # Count questions created by this user
                questions_query = select(func.count()).where(Question.author_id == user.id)
                questions_result = await session.execute(questions_query)
                questions_count = questions_result.scalar()
                
                # Count answers provided by this user (excluding skips)
                answers_query = select(func.count()).where(
                    Answer.user_id == user.id,
                    Answer.answer_type != "skip"
                )
                answers_result = await session.execute(answers_query)
                answers_count = answers_result.scalar()
                
                # Calculate points: 5 per question, 1 per answer
                question_points = questions_count * 5
                answer_points = answers_count * 1
                total_points = question_points + answer_points
                
                # Update user's points
                stmt = update(User).where(User.id == user.id).values(points=total_points)
                await session.execute(stmt)
                
                logger.info(
                    f"User {user.id} ({user.first_name}): "
                    f"{questions_count} questions (+{question_points}💎), "
                    f"{answers_count} answers (+{answer_points}💎), "
                    f"Total: {total_points}💎"
                )
            
            # Commit all changes
            await session.commit()
            logger.info("Points update completed successfully")
            
        except Exception as e:
            logger.error(f"Error updating points: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(update_points()) 