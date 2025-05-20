from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from src.db.models import Answer, Question
from src.db.repositories.base import BaseRepository


class AnswerRepository(BaseRepository[Answer]):
    def __init__(self):
        super().__init__(Answer)

    async def get_answer(self, session: AsyncSession, user_id: int, question_id: int) -> Answer | None:
        """Get a specific answer by user_id and question_id."""
        try:
            # Ensure session is refreshed before the query
            await session.commit()  # Commit any pending changes
            
            query = select(Answer).where(
                Answer.user_id == user_id,
                Answer.question_id == question_id
            )
            result = await session.execute(query)
            answer = result.scalar_one_or_none()
            
            logger.info(f"Retrieved answer for user {user_id}, question {question_id}: {answer is not None}")
            return answer
        except Exception as e:
            logger.error(f"Error in get_answer for user {user_id}, question {question_id}: {e}")
            return None

    async def save_answer(
        self, session: AsyncSession, user_id: int, question_id: int, answer_type: str, value: int
    ) -> Answer:
        """Saves or updates a user's answer to a question with robust error handling and transaction management."""
        try:
            # First commit any pending changes to ensure a clean session state
            await session.commit()
            
            # Check if answer already exists with a fresh query
            logger.info(f"Checking if answer exists for user {user_id}, question {question_id}")
            existing_answer = await self.get_answer(session, user_id, question_id)
            
            data = {
                "user_id": user_id,
                "question_id": question_id,
                "answer_type": answer_type,
                "value": value
            }
            
            logger.info(f"Saving answer for user {user_id}, question {question_id}, type: {answer_type}, value: {value}")
            
            if existing_answer:
                logger.info(f"Updating existing answer {existing_answer.id} for user {user_id}, question {question_id}")
                # Update existing answer
                updated_answer = await self.update(session, existing_answer.id, data)
                if not updated_answer:
                    logger.error(f"Failed to update existing answer {existing_answer.id}")
                    raise Exception("Failed to update existing answer")
                
                # Explicitly commit the update
                try:
                    await session.commit()
                    logger.info(f"Successfully committed answer update for user {user_id}, question {question_id}")
                except Exception as commit_error:
                    logger.error(f"Failed to commit answer update: {commit_error}", exc_info=True)
                    await session.rollback()
                    raise
                
                return updated_answer
            else:
                logger.info(f"Creating new answer for user {user_id}, question {question_id}")
                # Create new answer
                new_answer = await self.create(session, data)
                
                # Explicitly commit the creation
                try:
                    await session.commit()
                    logger.info(f"Successfully committed new answer for user {user_id}, question {question_id}")
                except Exception as commit_error:
                    logger.error(f"Failed to commit new answer: {commit_error}", exc_info=True)
                    await session.rollback()
                    raise
                
                return new_answer
        except Exception as e:
            logger.error(f"Error in save_answer for user {user_id}, question {question_id}: {e}", exc_info=True)
            # Ensure rollback on any error
            try:
                await session.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error}")
            
            # Re-raise to notify caller
            raise

    async def get_user_answers_for_group(self, session: AsyncSession, user_id: int, group_id: int) -> list[Answer]:
        """Get all answers from a user for questions in a specific group with improved reliability."""
        try:
            # Commit any pending changes to ensure we get the latest data
            await session.commit()
            
            # Fetch answers with a single optimized query
            query = select(Answer).join(
                Question, Answer.question_id == Question.id
            ).where(
                Answer.user_id == user_id,
                Question.group_id == group_id
            ).order_by(Answer.created_at.desc())
            
            logger.info(f"Fetching answers for user {user_id} in group {group_id}")
            result = await session.execute(query)
            answers = result.scalars().all()
            
            logger.info(f"Found {len(answers)} answers for user {user_id} in group {group_id}")
            return answers
        except Exception as e:
            logger.error(f"Error in get_user_answers_for_group for user {user_id}, group {group_id}: {e}", exc_info=True)
            return []

    async def get_answers_for_user_in_group(self, session: AsyncSession, user_id: int, group_id: int) -> list[Answer]:
        """Alias for get_user_answers_for_group for backward compatibility."""
        return await self.get_user_answers_for_group(session, user_id, group_id)


answer_repo = AnswerRepository() 