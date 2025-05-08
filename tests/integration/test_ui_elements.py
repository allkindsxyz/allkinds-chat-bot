import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.bot.handlers.start import on_instructions, on_group_info

@pytest.mark.ui_elements
async def test_instructions_button(
    test_session,
    test_user
):
    """Test that the instructions button shows the instructions."""
    # Create mocks for the message and its answer method
    mock_message = AsyncMock()
    mock_message.text = "📚 Instructions"
    mock_message.from_user.id = test_user.telegram_id
    
    # Create mock state
    mock_state = AsyncMock()
    
    with patch('src.db.get_session', return_value=test_session):
        # Call the handler
        await on_instructions(mock_message, mock_state)
        
        # Verify instructions were shown
        mock_message.answer.assert_called_once()
        
        # Get the first call's arguments and check content
        call_args = mock_message.answer.call_args[0]
        instruction_text = call_args[0]
        
        # Check key phrases that should be in the instructions
        assert "How to Use Allkinds" in instruction_text
        assert "Asking Questions" in instruction_text
        assert "Answering Questions" in instruction_text
        
        # Verify the message was formatted with HTML
        kwargs = mock_message.answer.call_args[1]
        assert kwargs.get("parse_mode") == "HTML"

@pytest.mark.skip("Requires more complex mocking of bot")
@pytest.mark.ui_elements
async def test_group_info_button(
    test_session,
    test_user,
    test_group
):
    """Test that the group info button shows group information."""
    # This test requires more complex mocking of the bot object
    # Skipping for now until we can properly set up the mock
    pass

@pytest.mark.ui_elements
async def test_question_notification(
    test_session,
    test_user,
    test_group,
    test_question,
    mock_bot
):
    """Test that question notifications are sent correctly."""
    from src.bot.handlers.start import send_question_notification
    from src.db.models import User, GroupMember, MemberRole
    
    # Create additional users to notify
    member1 = User(telegram_id=111111, first_name="Member1", username="member1")
    member2 = User(telegram_id=222222, first_name="Member2", username="member2")
    test_session.add_all([member1, member2])
    await test_session.commit()
    
    # Add them to the group
    members = [
        GroupMember(user_id=member1.id, group_id=test_group.id, role=MemberRole.MEMBER),
        GroupMember(user_id=member2.id, group_id=test_group.id, role=MemberRole.MEMBER)
    ]
    test_session.add_all(members)
    await test_session.commit()
    
    with patch('src.db.get_session', return_value=test_session):
        # Call the notification function
        await send_question_notification(mock_bot, test_question.id, test_group.id, test_session)
        
        # Verify notifications were sent to group members (excluding the author)
        assert mock_bot.send_message.call_count == 2
        
        # Verify the correct users received notifications
        recipient_ids = []
        for call in mock_bot.send_message.call_args_list:
            kwargs = call[1]
            recipient_ids.append(kwargs["chat_id"])
        
        assert member1.telegram_id in recipient_ids
        assert member2.telegram_id in recipient_ids
        # Author should NOT get a notification
        assert test_user.telegram_id not in recipient_ids 