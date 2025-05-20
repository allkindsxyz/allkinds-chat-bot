from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.db.models import Question, Answer
from src.db.repositories.base import BaseRepository
from src.core.question_categorizer import categorize_question
from src.core.diagnostics import track_db, IS_RAILWAY


class QuestionRepository(BaseRepository[Question]):
    def __init__(self):
        super().__init__(Question)

    @track_db
    async def create_question(
        self, session: AsyncSession, text: str, author_id: int, group_id: int
    ) -> Question:
        """Creates a new question with categorization."""
        # Categorize the question
        category = await categorize_question(text)
        
        question = await self.create(
            session,
            data={
                "text": text,
                "author_id": author_id,
                "group_id": group_id,
                "category": category,
                # Assuming default values for is_approved, is_active, counts etc.
            }
        )
        # Ensure the transaction is committed
        try:
            await session.commit()
        except Exception as e:
            logger.error(f"Error committing question creation transaction: {e}")
            await session.rollback()
            raise
            
        return question

    @track_db
    async def get_next_question_for_user(
        self, session: AsyncSession, user_id: int, group_id: int, excluded_ids: list[int] = None
    ) -> Question | None:
        """Gets the next unanswered question for a user in a group."""
        # Force a refresh of the session to ensure we have the latest data
        # This is especially important for PostgreSQL in Railway
        try:
            await session.commit()  # Commit any pending changes
            # Additional explicit flush to ensure all pending operations are processed
            await session.flush()
        except Exception as e:
            logger.warning(f"Error committing session before get_next_question_for_user: {e}")
        
        # Initialize excluded_ids if None
        if excluded_ids is None:
            excluded_ids = []
        
        # Get all answers from this user for questions in this group
        # to find questions they haven't answered yet
        try:
            # Get the specific user's answers directly with a SINGLE query for better reliability
            # This optimized query gets all answers for a user in a specific group in one go
            answers_query = (
                select(Answer)
                .join(Question, Question.id == Answer.question_id)
                .where(
                    Answer.user_id == user_id,
                    Question.group_id == group_id
                )
            )
            
            answers_result = await session.execute(answers_query)
            user_group_answers = answers_result.scalars().all()
            
            # Extract answered question IDs
            answered_ids = [a.question_id for a in user_group_answers]
            
            # Log for debugging
            logger.info(f"User {user_id} has answered {len(answered_ids)} questions in group {group_id}")
            logger.info(f"Answered question IDs: {answered_ids}")
            logger.info(f"Additional excluded IDs: {excluded_ids}")
            
            # Extra Railway logging
            if IS_RAILWAY:
                logger.info(f"RAILWAY DB DEBUG: answers_query SQL = {str(answers_query)}")
                logger.info(f"RAILWAY DB DEBUG: user_group_answers type = {type(user_group_answers)}")
            
            # Combine answered IDs with explicitly excluded IDs and ensure no duplicates
            all_excluded_ids = list(set(answered_ids + excluded_ids))
            
            # Select questions with a SINGLE query for better reliability
            # Get ALL eligible questions first, then we'll pick one randomly
            eligible_questions_query = (
                select(Question)
                .where(
                    Question.group_id == group_id,
                    Question.is_active == True,
                    ~Question.id.in_(all_excluded_ids) if all_excluded_ids else True
                )
                .order_by(Question.created_at.asc())  # Show questions by creation date (oldest first)
            )
            
            eligible_result = await session.execute(eligible_questions_query)
            eligible_questions = eligible_result.scalars().all()
            
            # Extra Railway logging
            if IS_RAILWAY:
                logger.info(f"RAILWAY DB DEBUG: eligible_questions_query SQL = {str(eligible_questions_query)}")
                logger.info(f"RAILWAY DB DEBUG: eligible_questions type = {type(eligible_questions)}")
            
            # Log the eligible questions for debugging
            eligible_question_ids = [q.id for q in eligible_questions]
            logger.info(f"Found {len(eligible_questions)} eligible questions for user {user_id} in group {group_id}")
            logger.info(f"Eligible question IDs: {eligible_question_ids}")
            
            # If we have no eligible questions, return None
            if not eligible_questions:
                logger.info(f"No eligible questions for user {user_id} in group {group_id}")
                return None
                
            # Take the first eligible question (oldest by creation date)
            question = eligible_questions[0]
            
            # Perform a final safety check to make absolutely sure we're not returning an answered question
            if question.id in answered_ids:
                logger.error(f"CRITICAL: Question {question.id} was already answered but was selected as next question. Returning None instead.")
                return None
                
            logger.info(f"Selected question {question.id} for user {user_id} in group {group_id}")
            
            # Refresh the question object from the database to ensure we have the latest data
            await session.refresh(question)
            
            return question
            
        except Exception as e:
            logger.error(f"Error in get_next_question_for_user: {e}", exc_info=True)
            # In case of error, return None rather than raising an exception
            return None

    @track_db
    async def get_group_questions(self, session: AsyncSession, group_id: int) -> list[Question]:
        """Get all questions for a specific group."""
        # Make sure we're retrieving ALL active questions for the group
        # with a clear, explicit query that doesn't depend on any user-specific filters
        query = select(Question).where(
            Question.group_id == group_id,
            Question.is_active == True
        ).order_by(Question.created_at.asc())  # Changed to ascending order (oldest first)
        
        result = await session.execute(query)
        questions = result.scalars().all()
        
        # Log the retrieval for debugging
        logger.info(f"Retrieved {len(questions)} active questions for group {group_id}")
        return questions

    @track_db
    async def get_all_active(self, session: AsyncSession) -> list[Question]:
        """Get all active questions across all groups."""
        query = select(Question).where(
            Question.is_active == True
        ).order_by(Question.created_at.desc())
        
        result = await session.execute(query)
        return result.scalars().all()

    @track_db
    async def mark_inactive(self, session: AsyncSession, question_id: int) -> bool:
        """Mark a question as inactive (soft delete)."""
        question = await self.get(session, question_id)
        if not question:
            return False
            
        # Update the question to set is_active = False
        updated = await self.update(session, question_id, {"is_active": False})
        return updated is not None

    @track_db
    async def mark_deleted(self, session: AsyncSession, question_id: int) -> bool:
        """Mark a question as deleted via Telegram (soft delete)."""
        # Simply use the mark_inactive method since they do the same thing
        return await self.mark_inactive(session, question_id)

    @track_db
    async def get_questions_by_ids(self, session: AsyncSession, question_ids: list[int]) -> list[Question]:
        """Get multiple questions by their IDs, sorted by creation date (oldest first)."""
        if not question_ids:
            return []
            
        query = select(Question).where(
            Question.id.in_(question_ids),
            Question.is_active == True
        ).order_by(Question.created_at.asc())  # Consistent with other functions - show oldest first
        
        result = await session.execute(query)
        questions = result.scalars().all()
        
        logger.info(f"Retrieved {len(questions)} questions by IDs (requested {len(question_ids)})")
        return questions


question_repo = QuestionRepository() 