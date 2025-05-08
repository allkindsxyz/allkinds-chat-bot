"""
Navigation handlers for the chat bot.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.user import user_repo

from .keyboards import get_chat_selection_keyboard
from .repositories import (
    get_active_chats_for_user,
    get_unread_message_count,
    get_partner_nickname
)
from .chat_handlers import show_main_menu

router = Router()

# Chat page navigation
@router.callback_query(F.data.startswith("page:"))
async def on_page_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle pagination for chat selection."""
    await callback.answer()
    
    page = int(callback.data.split(":")[1])
    
    user = await user_repo.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("You need to register in the main bot first.")
        return
        
    # Get all active chats
    active_chats = await get_active_chats_for_user(session, user.id)
    
    # Format users for keyboard
    users_data = []
    for chat in active_chats:
        # Determine partner ID
        partner_id = chat.recipient_id if chat.initiator_id == user.id else chat.initiator_id
        partner = await user_repo.get(session, partner_id)
        
        if not partner:
            continue
            
        # Get unread count
        unread_count = await get_unread_message_count(session, chat.id, user.id)
        
        # Get partner nickname
        partner_name = await get_partner_nickname(session, partner_id)
        
        users_data.append({
            "id": partner.id,
            "name": partner_name,
            "unread_count": unread_count
        })
    
    await callback.message.edit_text(
        "Select a user to chat with:",
        reply_markup=get_chat_selection_keyboard(users_data, page=page)
    )


# Handle noop callback (used for page indicators)
@router.callback_query(F.data == "noop")
async def on_noop(callback: CallbackQuery):
    """Handle noop callback without changing anything."""
    await callback.answer() 