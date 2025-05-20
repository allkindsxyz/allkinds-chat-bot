"""
User management functionality for the chat bot.
"""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.user import user_repo
from src.db.repositories.match_repo import get_match_between_users
from src.db.repositories.chat_session_repo import update_status
from src.db.repositories.chat_message_repo import chat_message_repo
from src.db.repositories.blocked_user_repo import blocked_user_repo

from .states import ChatState
from .keyboards import (
    get_select_user_to_manage_keyboard,
    get_user_management_keyboard,
    get_confirm_delete_keyboard,
    get_confirm_block_keyboard,
    get_back_to_menu_keyboard
)
from .repositories import (
    get_active_chats_for_user,
    get_partner_nickname
)

# Define placeholder for missing functions
get_chat_session_by_match = None

# Try to import the function if it exists
try:
    from .repositories import get_chat_session_by_match
except ImportError:
    logger.warning("get_chat_session_by_match not found in repositories. Some functionality may be limited.")
    
    # Define a placeholder function
    async def get_chat_session_by_match(session, match_id):
        logger.error(f"get_chat_session_by_match was called but is not implemented!")
        return None

from .chat_handlers import show_main_menu

router = Router()

# Manage users
@router.message(F.text == "⚙️ Manage users")
async def show_user_management(message: Message, state: FSMContext, session: AsyncSession):
    """Display list of users to manage."""
    user = await user_repo.get_by_telegram_user_id(session, message.from_user.id)
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
        
    # Get all active chats
    active_chats = await get_active_chats_for_user(session, user.id)
    
    if not active_chats:
        await message.answer(
            "You don't have any active chats to manage.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
        
    # Format users for keyboard
    users_data = []
    for chat in active_chats:
        # Determine partner ID
        partner_id = chat.recipient_id if chat.initiator_id == user.id else chat.initiator_id
        partner = await user_repo.get(session, partner_id)
        
        if not partner:
            continue
            
        # Get partner nickname
        partner_name = await get_partner_nickname(session, partner_id)
        
        users_data.append({
            "id": partner.id,
            "name": partner_name
        })
    
    await message.answer(
        "Select a user to manage:",
        reply_markup=get_select_user_to_manage_keyboard(users_data)
    )
    
    await state.set_state(ChatState.managing_users)


# User management selection callback
@router.callback_query(F.data.startswith("manage:"))
async def on_manage_user_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle selecting a user to manage."""
    await callback.answer()
    
    user = await user_repo.get_by_telegram_user_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("You need to register in the main bot first.")
        return
    
    partner_id = int(callback.data.split(":")[1])
    partner = await user_repo.get(session, partner_id)
    
    if not partner:
        await callback.message.answer("Partner not found.")
        return
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    await callback.message.edit_text(
        f"Manage your relationship with {partner_name}:",
        reply_markup=get_user_management_keyboard(partner_id)
    )


# Show username action
@router.callback_query(F.data.startswith("show_username:"))
async def on_show_username(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Reveal the username of a chat partner."""
    await callback.answer()
    
    user = await user_repo.get_by_telegram_user_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("You need to register in the main bot first.")
        return
    
    partner_id = int(callback.data.split(":")[1])
    partner = await user_repo.get(session, partner_id)
    
    if not partner:
        await callback.message.answer("Partner not found.")
        return
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    # Get partner username
    username = f"@{partner.username}" if partner.username else "No username set"
    
    await callback.message.edit_text(
        f"User information for {partner_name}:\n\n"
        f"Username: {username}\n\n"
        f"You can now contact them directly on Telegram.",
        reply_markup=get_user_management_keyboard(partner_id)
    )
    
    # Notify the partner
    partner_tg_user_id = partner.telegram_user_id
    if partner_tg_user_id:
        try:
            bot = callback.bot
            await bot.send_message(
                partner_tg_user_id,
                f"Your Telegram username was viewed."
            )
        except Exception as e:
            logger.error(f"Failed to notify user {partner_tg_user_id}: {e}")


# Delete match confirmation request
@router.callback_query(F.data.startswith("delete_match:"))
async def on_delete_match_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Show confirmation for deleting a match."""
    await callback.answer()
    
    partner_id = int(callback.data.split(":")[1])
    partner = await user_repo.get(session, partner_id)
    
    if not partner:
        await callback.message.answer("Partner not found.")
        return
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    await callback.message.edit_text(
        f"Are you sure you want to delete your match with {partner_name}?\n\n"
        "This will remove your chat history and you won't be matched again.",
        reply_markup=get_confirm_delete_keyboard(partner_id)
    )


# Block user confirmation request
@router.callback_query(F.data.startswith("block_user:"))
async def on_block_user_request(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Show confirmation for blocking a user."""
    await callback.answer()
    
    partner_id = int(callback.data.split(":")[1])
    partner = await user_repo.get(session, partner_id)
    
    if not partner:
        await callback.message.answer("Partner not found.")
        return
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    await callback.message.edit_text(
        f"Are you sure you want to block {partner_name}?\n\n"
        "They won't be able to contact you, and you won't be matched again.",
        reply_markup=get_confirm_block_keyboard(partner_id)
    )


# Confirm delete match
@router.callback_query(F.data.startswith("confirm_delete:"))
async def on_confirm_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Handle confirmation to delete a match."""
    await callback.answer()
    
    user = await user_repo.get_by_telegram_user_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("You need to register in the main bot first.")
        return
    
    partner_id = int(callback.data.split(":")[1])
    partner = await user_repo.get(session, partner_id)
    
    if not partner:
        await callback.message.answer("Partner not found.")
        return
    
    # Find the match
    match = await get_match_between_users(session, user.id, partner_id)
    if not match:
        await callback.message.answer("No match found with this user.")
        return
    
    # Find the chat session
    chat_session = await get_chat_session_by_match(session, match.id)
    
    if chat_session:
        # End the chat session
        await update_status(session, chat_session.id, "ended", set_ended=True)
        
        # Delete chat messages
        await chat_message_repo.delete_messages_for_chat(session, chat_session.id)
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    await callback.message.edit_text(
        f"Match with {partner_name} has been deleted.\n"
        "Chat history has been cleared.",
        reply_markup=None
    )
    
    # Notify partner
    partner_tg_user_id = partner.telegram_user_id
    if partner_tg_user_id:
        try:
            await bot.send_message(
                partner_tg_user_id,
                f"{user.first_name} has ended your match."
            )
        except Exception as e:
            logger.error(f"Failed to notify user {partner_tg_user_id}: {e}")
    
    # Return to main menu
    await show_main_menu(callback.message, state, session)


# Confirm block user
@router.callback_query(F.data.startswith("confirm_block:"))
async def on_confirm_block(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Handle confirmation to block a user."""
    await callback.answer()
    
    user = await user_repo.get_by_telegram_user_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("You need to register in the main bot first.")
        return
    
    partner_id = int(callback.data.split(":")[1])
    partner = await user_repo.get(session, partner_id)
    
    if not partner:
        await callback.message.answer("Partner not found.")
        return
    
    # Block the user
    await blocked_user_repo.block_user(session, user.id, partner_id)
    
    # Find the match
    match = await get_match_between_users(session, user.id, partner_id)
    
    if match:
        # Find the chat session
        chat_session = await get_chat_session_by_match(session, match.id)
        
        if chat_session:
            # End the chat session
            await update_status(session, chat_session.id, "ended", set_ended=True)
            
            # Delete chat messages
            await chat_message_repo.delete_messages_for_chat(session, chat_session.id)
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    await callback.message.edit_text(
        f"{partner_name} has been blocked.\n"
        "They won't be able to contact you, and you won't be matched again.",
        reply_markup=None
    )
    
    # Return to main menu
    await show_main_menu(callback.message, state, session)


# Back to menu from callback
@router.callback_query(F.data == "back_to_menu")
async def on_back_to_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle back to menu button click."""
    await callback.answer()
    await show_main_menu(callback.message, state, session)


# Manage users page navigation
@router.callback_query(F.data.startswith("manage_page:"))
async def on_manage_page_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle pagination for user management."""
    await callback.answer()
    
    page = int(callback.data.split(":")[1])
    
    user = await user_repo.get_by_telegram_user_id(session, callback.from_user.id)
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
            
        # Get partner nickname
        partner_name = await get_partner_nickname(session, partner_id)
        
        users_data.append({
            "id": partner.id,
            "name": partner_name
        })
    
    await callback.message.edit_text(
        "Select a user to manage:",
        reply_markup=get_select_user_to_manage_keyboard(users_data, page=page)
    ) 