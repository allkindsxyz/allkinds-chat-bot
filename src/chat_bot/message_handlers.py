"""
Message handling functionality for the chat bot.
"""
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey, BaseStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from src.db.models import Chat
from src.db.repositories.user import user_repo
from src.db.repositories.chat_message_repo import chat_message_repo
from src.chat_bot.chat_handlers import get_chat_by_id

from .states import ChatState
from .keyboards import get_in_chat_keyboard, get_whats_next_keyboard
from .repositories import get_partner_nickname


async def check_recipient_state(
    bot: Bot, 
    storage: BaseStorage,
    recipient_telegram_user_id: int,
    sender_name: str,
    chat_id: int,
    partner_id: int
) -> bool:
    """
    Check if recipient is in active chat with sender and notify if not.
    
    Args:
        bot: Bot instance
        storage: FSM storage
        recipient_telegram_user_id: Telegram User ID of the recipient
        sender_name: Name of the sender to show in notification
        chat_id: ID of the chat
        partner_id: ID of the partner (sender)
        
    Returns:
        True if notification was sent, False otherwise
    """
    try:
        # Create a key for the recipient's state
        key = StorageKey(bot_id=bot.id, user_id=recipient_telegram_user_id, chat_id=recipient_telegram_user_id)
        
        # Get the recipient's state
        state = await storage.get_state(key=key)
        
        # If they have no state or aren't in chat, send notification
        if state != ChatState.in_chat.state:
            # They're not in chat state, send notification
            logger.info(f"Sending notification to {recipient_telegram_user_id} about new message from {sender_name}")
            
            # Create deep link for direct chat access
            open_chat_data = {
                "chat_id": chat_id,
                "partner_id": partner_id
            }
            
            # Create inline keyboard with button to open chat
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📨 Open Chat",
                            callback_data=f"open_chat:{partner_id}:{chat_id}"
                        )
                    ]
                ]
            )
            
            # Send notification
            await bot.send_message(
                chat_id=recipient_telegram_user_id,
                text=f"📬 New message from {sender_name}!\n\nClick below to view and respond:",
                reply_markup=keyboard
            )
            return True
        else:
            # They're in a chat state, check if it's with this sender
            data = await storage.get_data(key=key)
            current_partner_id = data.get("partner_id")
            
            if current_partner_id != partner_id:
                # They're chatting with someone else, send notification
                logger.info(f"User {recipient_telegram_user_id} is chatting with someone else, sending notification")
                
                # Create inline keyboard with button to switch chat
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📨 Switch to this Chat",
                                callback_data=f"open_chat:{partner_id}:{chat_id}"
                            )
                        ]
                    ]
                )
                
                # Send notification
                await bot.send_message(
                    chat_id=recipient_telegram_user_id,
                    text=f"📬 New message from {sender_name} while you're chatting with someone else!\n\nClick below to switch to this conversation:",
                    reply_markup=keyboard
                )
                return True
                
            # They're already chatting with this sender, no need for notification
            return False
            
    except Exception as e:
        logger.error(f"Error checking recipient state: {e}")
        return False


router = Router()

# Handle text messages in chat
@router.message(ChatState.in_chat, F.text)
async def relay_text_message(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Relay text messages between paired users."""
    user_id = message.from_user.id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
    
    data = await state.get_data()
    partner_id = data.get("partner_id")
    
    if not partner_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    chat_id = data.get("chat_id")
    
    if not chat_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    # Get chat
    chat = await get_chat_by_id(session, chat_id)
    if not chat or chat.status != "active":
        await message.answer("This chat is no longer active.")
        await state.clear()
        return
    
    # Get partner
    partner = await user_repo.get(session, partner_id)
    if not partner or not partner.telegram_user_id:
        await message.answer("Cannot find your chat partner. They may have left.")
        return
    
    # Get sender's name for notification
    sender_name = await get_partner_nickname(session, user.id)
    
    # Save message to database
    new_message = await chat_message_repo.create_message(
        session,
        chat_id=chat_id,
        sender_id=user.id,
        content_type="text",
        text_content=message.text
    )
    
    # Check if we need to update the history message for the sender
    history_message_id = data.get("history_message_id")
    if history_message_id:
        try:
            # Format the new message for display
            timestamp = new_message.created_at.strftime("%H:%M")
            content = message.text.replace("<", "&lt;").replace(">", "&gt;")  # Escape HTML
            formatted_message = f"[{timestamp}] <b>You</b>: {content}\n\n"
            logger.info(f"Updating chat history with new message, history_id: {history_message_id}")
            
            # Get current history message
            try:
                history_message = await bot.get_message(
                    chat_id=user.telegram_user_id,
                    message_id=history_message_id
                )
                
                # Extract current text and append new message
                current_text = history_message.text or history_message.caption or ""
                
                # Check if the message starts with the header
                header = "<b>Message History:</b>\n\n"
                if current_text.startswith(header):
                    # Add the new message right after the header
                    header_end = len(header)
                    combined_text = current_text[:header_end] + formatted_message + current_text[header_end:]
                else:
                    # If no header found, simply append the new message
                    combined_text = current_text + formatted_message
                
                # Check if message is too long for Telegram's limits
                if len(combined_text) > 4000:
                    # If too long, truncate the middle part of the message, keeping recent and old messages
                    # Find a good break point - look for double newlines
                    cutoff_point = combined_text.find("\n\n", 1500)
                    if cutoff_point != -1:
                        combined_text = combined_text[:500] + "\n\n[...]\n\n" + combined_text[-3000:]
                    else:
                        # If we can't find a good break, just truncate
                        combined_text = combined_text[:500] + "\n\n[...]\n\n" + combined_text[-3000:]
                
                # Edit the history message
                await bot.edit_message_text(
                    chat_id=user.telegram_user_id,
                    message_id=history_message_id,
                    text=combined_text,
                    parse_mode="HTML"
                )
                logger.info(f"Successfully updated chat history message {history_message_id}")
            except Exception as e:
                logger.error(f"Failed to get or update history message: {e}")
        except Exception as e:
            logger.error(f"Error updating chat history: {e}")
    
    # Check if recipient needs a notification
    sent_notification = await check_recipient_state(
        bot=bot,
        storage=state.storage,
        recipient_telegram_user_id=partner.telegram_user_id,
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward message to partner
    await bot.send_message(
        chat_id=partner.telegram_user_id,
        text=message.text
    )

# Handle photo messages in chat
@router.message(ChatState.in_chat, F.photo)
async def relay_photo_message(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Relay photo messages between paired users."""
    user_id = message.from_user.id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
    
    data = await state.get_data()
    partner_id = data.get("partner_id")
    chat_id = data.get("chat_id")
    
    if not partner_id or not chat_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    # Get chat
    chat = await get_chat_by_id(session, chat_id)
    if not chat or chat.status != "active":
        await message.answer("This chat is no longer active.")
        await state.clear()
        return
    
    # Get partner
    partner = await user_repo.get(session, partner_id)
    if not partner or not partner.telegram_user_id:
        await message.answer("Cannot find your chat partner. They may have left.")
        return
    
    # Get the largest photo (best quality)
    photo = message.photo[-1]
    caption = message.caption or ""
    
    # Save message to database
    new_message = await chat_message_repo.create_message(
        session,
        chat_id=chat_id,
        sender_id=user.id,
        content_type="photo",
        text_content=caption,
        file_id=photo.file_id
    )
    
    # Get sender's name for notification
    sender_name = await get_partner_nickname(session, user.id)
    
    # Check if recipient needs a notification
    sent_notification = await check_recipient_state(
        bot=bot,
        storage=state.storage,
        recipient_telegram_user_id=partner.telegram_user_id,
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward photo to partner
    await bot.send_photo(
        chat_id=partner.telegram_user_id,
        photo=photo.file_id,
        caption=caption
    )

# Handle document messages in chat
@router.message(ChatState.in_chat, F.document)
async def relay_document_message(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Relay document messages between paired users."""
    user_id = message.from_user.id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
    
    data = await state.get_data()
    partner_id = data.get("partner_id")
    chat_id = data.get("chat_id")
    
    if not partner_id or not chat_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    # Get chat
    chat = await get_chat_by_id(session, chat_id)
    if not chat or chat.status != "active":
        await message.answer("This chat is no longer active.")
        await state.clear()
        return
    
    # Get partner
    partner = await user_repo.get(session, partner_id)
    if not partner or not partner.telegram_user_id:
        await message.answer("Cannot find your chat partner. They may have left.")
        return
    
    # Get document
    document = message.document
    caption = message.caption or ""
    
    # Save message to database
    new_message = await chat_message_repo.create_message(
        session,
        chat_id=chat_id,
        sender_id=user.id,
        content_type="document",
        text_content=caption,
        file_id=document.file_id
    )
    
    # Get sender's name for notification
    sender_name = await get_partner_nickname(session, user.id)
    
    # Check if recipient needs a notification
    sent_notification = await check_recipient_state(
        bot=bot,
        storage=state.storage,
        recipient_telegram_user_id=partner.telegram_user_id,
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward document to partner
    await bot.send_document(
        chat_id=partner.telegram_user_id,
        document=document.file_id,
        caption=caption
    )

# Handle sticker messages in chat
@router.message(ChatState.in_chat, F.sticker)
async def relay_sticker_message(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Relay sticker messages between paired users."""
    user_id = message.from_user.id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
    
    data = await state.get_data()
    partner_id = data.get("partner_id")
    chat_id = data.get("chat_id")
    
    if not partner_id or not chat_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    # Get chat
    chat = await get_chat_by_id(session, chat_id)
    if not chat or chat.status != "active":
        await message.answer("This chat is no longer active.")
        await state.clear()
        return
    
    # Get partner
    partner = await user_repo.get(session, partner_id)
    if not partner or not partner.telegram_user_id:
        await message.answer("Cannot find your chat partner. They may have left.")
        return
    
    # Get sticker
    sticker = message.sticker
    
    # Save message to database
    new_message = await chat_message_repo.create_message(
        session,
        chat_id=chat_id,
        sender_id=user.id,
        content_type="sticker",
        file_id=sticker.file_id
    )
    
    # Get sender's name for notification
    sender_name = await get_partner_nickname(session, user.id)
    
    # Check if recipient needs a notification
    sent_notification = await check_recipient_state(
        bot=bot,
        storage=state.storage,
        recipient_telegram_user_id=partner.telegram_user_id,
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward sticker to partner
    await bot.send_sticker(
        chat_id=partner.telegram_user_id,
        sticker=sticker.file_id
    )

# Handle voice messages in chat
@router.message(ChatState.in_chat, F.voice)
async def relay_voice_message(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Relay voice messages between paired users."""
    user_id = message.from_user.id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
    
    data = await state.get_data()
    partner_id = data.get("partner_id")
    chat_id = data.get("chat_id")
    
    if not partner_id or not chat_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    # Get chat
    chat = await get_chat_by_id(session, chat_id)
    if not chat or chat.status != "active":
        await message.answer("This chat is no longer active.")
        await state.clear()
        return
    
    # Get partner
    partner = await user_repo.get(session, partner_id)
    if not partner or not partner.telegram_user_id:
        await message.answer("Cannot find your chat partner. They may have left.")
        return
    
    # Get voice
    voice = message.voice
    
    # Save message to database
    new_message = await chat_message_repo.create_message(
        session,
        chat_id=chat_id,
        sender_id=user.id,
        content_type="voice",
        file_id=voice.file_id
    )
    
    # Get sender's name for notification
    sender_name = await get_partner_nickname(session, user.id)
    
    # Check if recipient needs a notification
    sent_notification = await check_recipient_state(
        bot=bot,
        storage=state.storage,
        recipient_telegram_user_id=partner.telegram_user_id,
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward voice to partner
    await bot.send_voice(
        chat_id=partner.telegram_user_id,
        voice=voice.file_id
    )

# Handle the "Choose What's Next" button
@router.message(ChatState.in_chat, lambda message: message.text.startswith("🙌 Choose What's Next") or message.text.startswith("🙌 What's next with"))
async def handle_whats_next(message: Message, state: FSMContext, session: AsyncSession):
    """Handle the user clicking the What's Next buttons (both old and new formats)."""
    user_id = message.from_user.id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
    
    data = await state.get_data()
    partner_id = data.get("partner_id")
    
    if not partner_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    # Get partner
    partner = await user_repo.get(session, partner_id)
    if not partner:
        await message.answer("Partner not found.")
        return
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    await message.answer(
        f"What would you like to do with your chat with {partner_name}?",
        reply_markup=get_whats_next_keyboard(partner_id)
    )

# Handle "Keep Chatting" option
@router.callback_query(F.data.startswith("next_keep_chatting:"))
async def on_keep_chatting(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle user choosing to keep chatting."""
    await callback.answer()
    
    partner_id = int(callback.data.split(":")[1])
    partner = await user_repo.get(session, partner_id)
    
    if not partner:
        await callback.message.answer("Partner not found.")
        return
    
    # Get partner nickname
    partner_name = await get_partner_nickname(session, partner_id)
    
    await callback.message.edit_text(
        f"You've chosen to continue chatting with {partner_name}. Just type your messages as usual.",
        reply_markup=None
    )

# Handle "Connect Directly" option
@router.callback_query(F.data.startswith("next_connect_directly:"))
async def on_connect_directly(query: types.CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    """Handler for the Share my Telegram account button."""
    try:
        logger.info(f"Share Telegram account button clicked. Data: {query.data}")
        
        # Parse the callback data to get the partner ID
        partner_id = int(query.data.split(":")[1])
        logger.info(f"Partner ID extracted: {partner_id}")
        
        # Get User A's information (the one who clicked the button)
        user_a_id = query.from_user.id
        user_a = await user_repo.get_by_telegram_user_id(session, user_a_id)
        
        if not user_a:
            logger.error(f"User A with telegram_user_id {user_a_id} not found in database")
            await query.answer("You need to be registered to use this feature")
            return
        
        # Get user A nickname from the helper function
        user_a_nickname = await get_partner_nickname(session, user_a.id)
        logger.info(f"User A found: {user_a.id} (nickname: {user_a_nickname})")
        
        # Get partner (User B) information
        partner = await user_repo.get(session, partner_id)
        if not partner:
            logger.error(f"Partner with ID {partner_id} not found in database")
            await query.answer("Partner not found")
            return
        
        # Get partner nickname from the helper function
        partner_nickname = await get_partner_nickname(session, partner.id)
        logger.info(f"Partner found: {partner.id} (nickname: {partner_nickname}, telegram_user_id: {partner.telegram_user_id})")
        
        # Get data needed for messaging
        data = await state.get_data()
        chat_id = data.get("chat_id")
        logger.info(f"Chat ID from state: {chat_id}")
        
        # Get User A's username
        user_a_username = query.from_user.username
        
        # Format the message for sharing User A's information
        from aiogram.utils.text_decorations import escape_html
        user_info_message = f"I'd like to connect directly.\n\nMy nickname: {escape_html(user_a_nickname)}"
        if user_a_username:
            user_info_message += f"\nMy Telegram: @{escape_html(user_a_username)}"
        
        logger.info(f"Prepared user info message: {user_info_message}")
        
        # Send confirmation to User A
        try:
            await query.message.edit_text(
                f"You've shared your Telegram account information with {partner_nickname}.",
                reply_markup=None
            )
            logger.info("Confirmation sent to User A")
        except Exception as e:
            logger.error(f"Error sending confirmation to User A: {e}")
            # Try to send a new message if editing fails
            await query.message.answer(
                f"You've shared your Telegram account information with {partner_nickname}."
            )
        
        # Send User A's info to User B (partner)
        if partner.telegram_user_id:
            try:
                notification_message = f"Your match {user_a_nickname} has shared their contact information:\n\n{user_info_message}"
                logger.info(f"Sending notification to partner at telegram_user_id {partner.telegram_user_id}")
                
                sent_message = await bot.send_message(
                    chat_id=partner.telegram_user_id,
                    text=notification_message,
                    parse_mode="HTML"
                )
                
                logger.info(f"Message sent to partner successfully: {sent_message.message_id}")
                
                # Also save this as a message in the chat
                if chat_id:
                    new_message = await chat_message_repo.create_message(
                        session,
                        chat_id=chat_id,
                        sender_id=user_a.id,
                        content_type="text",
                        text_content=user_info_message
                    )
                    logger.info(f"Message saved to chat history, ID: {new_message.id}")
                else:
                    logger.error("Could not save message to chat history: chat_id is None")
                
                logger.info(f"User {user_a.id} shared contact information with partner {partner_id}")
            except Exception as e:
                logger.error(f"Failed to send contact information to user {partner.telegram_user_id}: {e}")
                await query.message.answer(f"Error sending your contact information to your match: {str(e)}")
        else:
            logger.error(f"Partner {partner_id} has no telegram_user_id, cannot send notification")
            await query.message.answer("Your match doesn't have a Telegram ID. Unable to send your contact information.")
        
        # Acknowledge the query
        await query.answer("Your information has been shared")
    
    except Exception as e:
        import traceback
        logger.error(f"Unexpected error in on_connect_directly: {e}")
        logger.error(traceback.format_exc())
        await query.answer("An error occurred. Please try again.") 