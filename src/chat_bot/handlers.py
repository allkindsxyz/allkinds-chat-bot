"""
Register all handlers for the chat bot.
"""
from aiogram import Router, Dispatcher
from loguru import logger

from .user_management import router as user_management_router
from .chat_handlers import router as chat_router
from .new_handlers import router as message_router

# Create a single router to combine all routers
main_router = Router()


def register_handlers(dp: Dispatcher) -> None:
    """
    Register all handlers for the chat bot.
    
    Args:
        dp: Dispatcher instance
    """
    logger.info("Registering chat bot handlers")
    
    # Include all routers
    main_router.include_router(chat_router)
    main_router.include_router(message_router)
    main_router.include_router(user_management_router)
    
    # Include main router in dispatcher
    dp.include_router(main_router)
    
    logger.info("Registered all chat bot handlers") 