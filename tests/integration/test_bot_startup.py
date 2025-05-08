import pytest
from unittest.mock import patch, AsyncMock
import asyncio

@pytest.mark.bot_start
async def test_bot_starts():
    """Test that the bot starts correctly."""
    from src.bot.main import start_bot
    
    # Mock the dispatcher's start_polling method
    mock_start_polling = AsyncMock()
    
    # Patch the necessary dependencies
    with patch('aiogram.Dispatcher.start_polling', mock_start_polling), \
         patch('src.bot.handlers.register_handlers'):
        
        # Create a task for start_bot but don't actually wait for it to complete
        # because it's designed to run forever
        task = asyncio.create_task(start_bot())
        
        # Give it a moment to start up
        await asyncio.sleep(0.1)
        
        # Cancel the task since we don't want to actually run the bot
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Verify that start_polling was called
        assert mock_start_polling.called 