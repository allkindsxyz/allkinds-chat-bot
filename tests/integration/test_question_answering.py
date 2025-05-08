import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from src.db.models import Answer, AnswerType
from src.bot.handlers.start import process_answer_callback, ANSWER_VALUES

@pytest.mark.question_answering
async def test_answer_question(
    test_session,
    test_user,
    test_group,
    test_question,
    mock_callback_query,
    mock_state
):
    """Test answering a question."""
    # Setup the callback query
    mock_callback_query.data = f"answer:{test_question.id}:1"  # Answer "Yes"
    mock_callback_query.from_user.id = test_user.telegram_id
    
    # Setup state
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name
    }
    
    with patch('src.db.get_session', return_value=test_session):
        # Call the handler
        await process_answer_callback(mock_callback_query, mock_state, test_session)
        
        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()
        
        # Check if the answer was stored in the database
        async with test_session.begin():
            query = select(Answer).where(
                Answer.question_id == test_question.id,
                Answer.user_id == test_user.id
            )
            result = await test_session.execute(query)
            answers = result.scalars().all()
            
            assert len(answers) == 1
            assert answers[0].value == 1  # Yes
            assert answers[0].type == AnswerType.NORMAL

@pytest.mark.question_answering
async def test_change_answer(
    test_session,
    test_user,
    test_group,
    test_question,
    mock_callback_query,
    mock_state
):
    """Test changing an existing answer."""
    # First create an initial answer
    answer = Answer(
        user_id=test_user.id,
        question_id=test_question.id,
        value=-1,  # Initial answer: No
        type=AnswerType.NORMAL
    )
    test_session.add(answer)
    await test_session.commit()
    
    # Setup the callback query for changing the answer
    mock_callback_query.data = f"answer:{test_question.id}:2"  # Change to "Strong Yes"
    mock_callback_query.from_user.id = test_user.telegram_id
    
    # Setup state
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name
    }
    
    with patch('src.db.get_session', return_value=test_session):
        # Call the handler
        await process_answer_callback(mock_callback_query, mock_state, test_session)
        
        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()
        
        # Check if the answer was updated in the database
        async with test_session.begin():
            query = select(Answer).where(
                Answer.question_id == test_question.id,
                Answer.user_id == test_user.id
            )
            result = await test_session.execute(query)
            answers = result.scalars().all()
            
            assert len(answers) == 1
            assert answers[0].value == 2  # Strong Yes (changed from No)
            assert answers[0].type == AnswerType.NORMAL

@pytest.mark.question_answering
async def test_skip_question(
    test_session,
    test_user,
    test_group,
    test_question,
    mock_callback_query,
    mock_state
):
    """Test skipping a question."""
    from src.bot.handlers.start import on_skip_question
    
    # Setup the callback query
    mock_callback_query.data = f"skip_question:{test_question.id}"
    mock_callback_query.from_user.id = test_user.telegram_id
    
    # Setup state
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name
    }
    
    with patch('src.db.get_session', return_value=test_session):
        # Call the handler
        await on_skip_question(mock_callback_query, mock_state, test_session)
        
        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()
        
        # Check if the skip was recorded in the database
        async with test_session.begin():
            query = select(Answer).where(
                Answer.question_id == test_question.id,
                Answer.user_id == test_user.id
            )
            result = await test_session.execute(query)
            answers = result.scalars().all()
            
            assert len(answers) == 1
            assert answers[0].value == 0  # Skip
            assert answers[0].type == AnswerType.SKIP 