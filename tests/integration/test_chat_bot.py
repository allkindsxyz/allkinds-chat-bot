import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.db.models import ChatMessage
from sqlalchemy import select

@pytest.mark.asyncio
async def test_chat_session_creation(
    test_session,
    test_user,
    test_user2,
    test_match
):
    """Test that a chat session can be created between matched users."""
    
    # Create a chat session
    chat_session = await create_chat_session(test_session, test_match.id)
    
    # Verify the chat session was created
    assert chat_session is not None
    assert chat_session.match_id == test_match.id
    assert chat_session.status == "active"

@pytest.mark.asyncio
async def test_message_sending(
    test_session,
    test_user,
    test_user2,
    test_match,
    test_chat_session
):
    """Test that messages can be sent in a chat session."""
    from src.db.repositories.chat_message_repo import create_message
    
    # Create a message
    message_text = "Hello from test user"
    message = await create_message(
        test_session,
        test_chat_session.id,
        test_user.id,
        message_text
    )
    
    # Verify the message was created
    assert message is not None
    assert message.session_id == test_chat_session.id
    assert message.sender_id == test_user.id
    assert message.content == message_text
    
    # Verify we can retrieve the message
    query = select(ChatMessage).where(ChatMessage.session_id == test_chat_session.id)
    result = await test_session.execute(query)
    messages = result.scalars().all()
    
    assert len(messages) == 1
    assert messages[0].id == message.id
    assert messages[0].content == message_text 