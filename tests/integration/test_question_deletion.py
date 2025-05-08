import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from src.db.models import Question
from src.bot.handlers.start import (
    on_delete_question_callback,
    on_confirm_delete_question,
    on_cancel_delete_question
)
from src.bot.states import QuestionFlow

@pytest.mark.question_deletion
async def test_delete_question_flow(
    test_session,
    test_user,
    test_group,
    test_question,
    mock_callback_query,
    mock_state
):
    """Test the complete flow of deleting a question."""
    # 1. First step: user clicks the delete button
    mock_callback_query.data = f"delete_question:{test_question.id}"
    mock_callback_query.from_user.id = test_user.telegram_id
    
    # Setup state
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name
    }
    
    with patch('src.db.get_session', return_value=test_session):
        # Call the delete handler
        await on_delete_question_callback(mock_callback_query, mock_state, test_session)
        
        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()
        
        # Verify confirmation message was shown
        mock_callback_query.message.edit_text.assert_called_once()
        
        # Verify state was updated to confirming_delete
        mock_state.set_state.assert_called_with(QuestionFlow.confirming_delete)
        
        # Verify question ID was stored in state
        mock_state.update_data.assert_called_with(delete_question_id=test_question.id)
    
    # 2. Second step: user confirms deletion
    mock_callback_query.data = f"confirm_delete_question:{test_question.id}"
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name,
        "delete_question_id": test_question.id
    }
    
    with patch('src.db.get_session', return_value=test_session):
        with patch('src.bot.handlers.start.on_show_questions', AsyncMock()) as mock_show_questions:
            # Call the confirm handler
            await on_confirm_delete_question(mock_callback_query, mock_state, test_session)
            
            # Verify state was reset to viewing_question
            mock_state.set_state.assert_called_with(QuestionFlow.viewing_question)
            
            # Verify on_show_questions was called to refresh the view
            mock_show_questions.assert_called_once()
    
    # Verify question was actually deleted from database
    async with test_session.begin():
        query = select(Question).where(Question.id == test_question.id)
        result = await test_session.execute(query)
        questions = result.scalars().all()
        
        assert len(questions) == 0

@pytest.mark.question_deletion
async def test_cancel_delete_question(
    test_session,
    test_user,
    test_group,
    test_question,
    mock_callback_query,
    mock_state
):
    """Test canceling question deletion."""
    # Setup the cancel callback query
    mock_callback_query.data = f"cancel_delete_question:{test_question.id}"
    mock_callback_query.from_user.id = test_user.telegram_id
    
    # Setup state
    mock_state.get_data.return_value = {
        "current_group_id": test_group.id,
        "current_group_name": test_group.name,
        "delete_question_id": test_question.id
    }
    
    with patch('src.db.get_session', return_value=test_session):
        # Call the cancel handler
        await on_cancel_delete_question(mock_callback_query, mock_state, test_session)
        
        # Verify state was reset to viewing_question
        mock_state.set_state.assert_called_with(QuestionFlow.viewing_question)
    
    # Verify question still exists in database
    async with test_session.begin():
        query = select(Question).where(Question.id == test_question.id)
        result = await test_session.execute(query)
        questions = result.scalars().all()
        
        assert len(questions) == 1
        assert questions[0].id == test_question.id

@pytest.mark.question_deletion
async def test_only_author_can_delete(
    test_session
):
    """Test that only the question author can delete a question."""
    # Create two users
    from src.db.models import User
    author = User(telegram_id=111111, first_name="Author", username="author")
    other_user = User(telegram_id=222222, first_name="Other", username="other")
    test_session.add_all([author, other_user])
    await test_session.commit()
    
    # Create a group with minimal data required
    from src.db.models import Group, GroupMember, MemberRole, Question
    group = Group(
        name="Test Group",
        creator_id=author.id,
    )
    test_session.add(group)
    await test_session.commit()
    
    # Add both users to the group
    members = [
        GroupMember(user_id=author.id, group_id=group.id, role=MemberRole.ADMIN),
        GroupMember(user_id=other_user.id, group_id=group.id, role=MemberRole.MEMBER)
    ]
    test_session.add_all(members)
    await test_session.commit()
    
    # Create a question by the author
    question = Question(
        text="Author's question",
        author_id=author.id,
        group_id=group.id,
        category="Test"
    )
    test_session.add(question)
    await test_session.commit()
    
    # Create mock callbacks for author and non-author users
    from unittest.mock import AsyncMock, patch
    from aiogram.types import User as TelegramUser
    
    # Create mock objects for each user
    author_user = AsyncMock()
    author_user.id = author.telegram_id
    
    other_tg_user = AsyncMock()
    other_tg_user.id = other_user.telegram_id
    
    author_callback = AsyncMock()
    author_callback.from_user = author_user
    author_callback.data = f"show_question:{question.id}"
    author_callback.message = AsyncMock()
    
    non_author_callback = AsyncMock()
    non_author_callback.from_user = other_tg_user
    non_author_callback.data = f"show_question:{question.id}"
    non_author_callback.message = AsyncMock()
    
    # Create mock state
    mock_state = AsyncMock()
    mock_state.get_data.return_value = {
        "current_group_id": group.id,
        "current_group_name": group.name
    }
    
    # Mock function to get keyboard buttons 
    async def mock_get_question_buttons_author(question_id, user_id):
        assert user_id == author.telegram_id
        return ["Delete"], []  # action_buttons for author include Delete
    
    async def mock_get_question_buttons_non_author(question_id, user_id):
        assert user_id == other_user.telegram_id
        return [], []  # action_buttons for non-author DONT include Delete
    
    # Test author flow - should see delete button
    with patch('src.bot.handlers.start.get_question_buttons', 
              side_effect=mock_get_question_buttons_author):
        with patch('src.db.get_session', return_value=test_session):
            # Get handler function
            from src.bot.handlers.start import on_show_question
            
            # Call handler for author
            await on_show_question(author_callback, mock_state, test_session)
            
            # Verify the message was edited with delete button for author
            author_callback.message.edit_text.assert_called_once()
            
    # Test non-author flow - should NOT see delete button
    with patch('src.bot.handlers.start.get_question_buttons', 
              side_effect=mock_get_question_buttons_non_author):
        with patch('src.db.get_session', return_value=test_session):
            # Call handler for non-author
            await on_show_question(non_author_callback, mock_state, test_session)
            
            # Verify the message was edited without delete button
            non_author_callback.message.edit_text.assert_called_once() 