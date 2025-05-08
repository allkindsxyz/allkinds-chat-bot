import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import User as TelegramUser, Chat, Message, CallbackQuery

@pytest.fixture
def telegram_user():
    """Create a mock Telegram user."""
    return TelegramUser(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="en",
    )

@pytest.fixture
def telegram_chat():
    """Create a mock Telegram chat."""
    return Chat(
        id=123456789,
        type="private",
        title=None,
        username="testuser",
        first_name="Test",
        last_name="User",
    )

@pytest.fixture
def mock_message(telegram_user, telegram_chat):
    """Create a mock message."""
    return Message(
        message_id=1,
        date=1617282480,
        chat=telegram_chat,
        from_user=telegram_user,
        sender_chat=None,
        text="Test message",
    )

@pytest.fixture
def mock_callback_query(telegram_user, mock_message):
    """Create a mock callback query."""
    return CallbackQuery(
        id="1",
        from_user=telegram_user,
        chat_instance="1",
        message=mock_message,
        data="test_data",
    )

@pytest.fixture
async def mock_bot():
    """Create a mock bot."""
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.delete_message = AsyncMock()
    return bot

@pytest.fixture
async def mock_dispatcher():
    """Create a mock dispatcher with memory storage."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    return dp

@pytest.fixture
def mock_state():
    """Create a mock FSM context state."""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.get_state = AsyncMock()
    state.clear = AsyncMock()
    return state

@pytest.fixture
def register_handlers_patch():
    """Patch the register_handlers function to avoid actually registering handlers during tests."""
    with patch('src.bot.handlers.register_handlers') as mock:
        yield mock

@pytest.fixture
def db_session_middleware_patch(test_session):
    """Patch the database session middleware to use the test session."""
    with patch('src.db.get_session', return_value=test_session) as mock:
        yield mock 