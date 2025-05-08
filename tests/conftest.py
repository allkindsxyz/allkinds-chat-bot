import pytest
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import fixtures so they're available to all tests
from tests.fixtures.database import (
    test_engine,
    test_session_maker,
    test_session,
    test_user,
    test_group,
    test_question,
)

from tests.fixtures.bot import (
    telegram_user,
    telegram_chat,
    mock_message,
    mock_callback_query,
    mock_bot,
    mock_dispatcher,
    mock_state,
    register_handlers_patch,
    db_session_middleware_patch,
)

# Configure pytest
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "bot_start: tests related to bot startup"
    )
    config.addinivalue_line(
        "markers", "question_creation: tests related to creating questions"
    )
    config.addinivalue_line(
        "markers", "question_answering: tests related to answering questions"
    )
    config.addinivalue_line(
        "markers", "question_deletion: tests related to deleting questions"
    )
    config.addinivalue_line(
        "markers", "match_finding: tests related to finding matches"
    )
    config.addinivalue_line(
        "markers", "ui_elements: tests related to UI elements like buttons and displays"
    ) 