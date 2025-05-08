import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from src.db.models import Question
from src.bot.states import QuestionFlow
from src.bot.handlers.start import (
    on_add_question,
    process_new_question_text,
    on_confirm_add_question
)

@pytest.mark.question_creation
async def test_add_question_flow(
    test_session,
    test_user,
    test_group,
    mock_message,
    mock_state,
    mock_bot
):
    """Test the complete flow of adding a question."""
    # Setup mock state with group ID
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name
    }
    
    # 1. First step: user clicks "Add Question" button
    with patch('src.db.get_session', return_value=test_session):
        # Mock the necessary functions
        with patch('src.bot.handlers.start.show_group_menu', AsyncMock()) as mock_show_menu:
            # Call the handler
            await on_add_question(mock_message, mock_state)
            
            # Check if state was updated correctly
            mock_state.set_state.assert_called_with(QuestionFlow.creating_question)
            mock_show_menu.assert_called_once()
    
    # 2. Second step: user enters question text
    mock_message.text = "Is teamwork important for productivity?"
    
    # Mock state data for the question creation flow
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name,
        "question_prompt_msg_id": 123,
    }
    
    # Mock check_spelling to return no errors
    with patch('src.core.openai_service.check_spelling', 
               AsyncMock(return_value=(False, ""))):
        # Mock is_yes_no_question to return True
        with patch('src.core.openai_service.is_yes_no_question', 
                  AsyncMock(return_value=True)):
            # Mock check_duplicate_question to return false (not a duplicate)
            with patch('src.core.openai_service.check_duplicate_question', 
                      AsyncMock(return_value=(False, []))):
                with patch('src.db.get_session', return_value=test_session):
                    await process_new_question_text(mock_message, mock_state, test_session)
                    
                    # Verify state was updated with question text
                    mock_state.update_data.assert_called()
                    
                    # Verify answers were presented for confirmation
                    mock_message.answer.assert_called()
    
    # 3. Third step: user confirms the question
    # Setup state for confirmation
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "new_question_text": "Is teamwork important for productivity?",
        "confirmation_msg_id": 456,
    }
    
    # Create a mock callback query for confirmation
    mock_callback = AsyncMock()
    mock_callback.message = mock_message
    mock_callback.data = "confirm_add_question"
    mock_callback.from_user = mock_message.from_user
    
    with patch('src.db.get_session', return_value=test_session):
        # Mock the send_question_notification function
        with patch('src.bot.handlers.start.send_question_notification', AsyncMock()) as mock_notify:
            # Mock the show_questions function
            with patch('src.bot.handlers.start.on_show_questions', AsyncMock()) as mock_show_questions:
                await on_confirm_add_question(mock_callback, mock_state, test_session)
                
                # Verify state was reset to viewing_question
                mock_state.set_state.assert_called_with(QuestionFlow.viewing_question)
                
                # Verify notification was sent
                mock_notify.assert_called_once()
                
                # Verify questions are shown after adding
                mock_show_questions.assert_called_once()
    
    # Verify the question was actually added to the database
    async with test_session.begin():
        query = select(Question).where(
            Question.group_id == test_group.id,
            Question.author_id == test_user.id
        )
        result = await test_session.execute(query)
        questions = result.scalars().all()
        
        assert len(questions) == 1
        assert questions[0].text == "Is teamwork important for productivity?" 