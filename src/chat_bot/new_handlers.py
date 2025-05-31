# Implementing new chat bot handlers

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
                text=f"�� New message from {sender_name}!\n\nClick below to view and respond:",
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

# Handle "Choose What's Next" button
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
async def on_connect_directly(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Handle user choosing to share their own telegram account."""
    try:
        await callback.answer()
        logger.info(f"Share Telegram account button clicked. Data: {callback.data}")
        
        # Get User A's information (the one who clicked the button)
        user_a = await user_repo.get_by_telegram_user_id(session, callback.from_user.id)
        
        if not user_a:
            logger.error(f"User A with telegram_user_id {callback.from_user.id} not found in database")
            await callback.message.answer("You need to be registered to use this feature")
            return
        
        # Get user A nickname from the helper function
        user_a_nickname = await get_partner_nickname(session, user_a.id)
        logger.info(f"User A found: {user_a.id} (nickname: {user_a_nickname})")
        
        # Parse partner ID (User B)
        partner_id = int(callback.data.split(":")[1])
        logger.info(f"Partner ID extracted: {partner_id}")
        
        partner = await user_repo.get(session, partner_id)
        
        if not partner:
            logger.error(f"Partner with ID {partner_id} not found in database")
            await callback.message.answer("Partner not found.")
            return
        
        # Get partner nickname from the helper function
        partner_nickname = await get_partner_nickname(session, partner.id)
        logger.info(f"Partner found: {partner.id} (nickname: {partner_nickname}, telegram_user_id: {partner.telegram_user_id})")
        
        # Get data needed for messaging
        data = await state.get_data()
        chat_id = data.get("chat_id")
        logger.info(f"Chat ID from state: {chat_id}")
        
        # Get User A's username
        user_a_username = callback.from_user.username
        
        # Format the message for sharing User A's information
        user_info_message = f"I'd like to connect directly.\n\nMy nickname: {user_a_nickname}"
        if user_a_username:
            user_info_message += f"\nMy Telegram: @{user_a_username}"
        
        logger.info(f"Prepared user info message: {user_info_message}")
        
        # Send confirmation to User A
        try:
            await callback.message.edit_text(
                f"You've shared your Telegram account information with {partner_nickname}.",
                reply_markup=None
            )
            logger.info("Confirmation sent to User A")
        except Exception as e:
            logger.error(f"Error sending confirmation to User A: {e}")
            # Try to send a new message if editing fails
            await callback.message.answer(
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
                await callback.message.answer(f"Error sending your contact information to your match: {str(e)}")
        else:
            logger.error(f"Partner {partner_id} has no telegram_user_id, cannot send notification")
            await callback.message.answer("Your match doesn't have a Telegram ID. Unable to send your contact information.")
    
    except Exception as e:
        import traceback
        logger.error(f"Unexpected error in on_connect_directly: {e}")
        logger.error(traceback.format_exc())
        await callback.answer("An error occurred. Please try again.")

# Handle text messages in chat
@router.message(ChatState.in_chat, F.text)
async def relay_text_message(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Relay text messages between paired users."""
    # Skip special command messages
    if message.text.startswith("🙌 Choose What's Next") or message.text.startswith("🙌 What's next with") or message.text.startswith("🔙 Back to menu") or message.text == "👥 Switch chat":
        return
        
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
    if not partner:
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
    
    # Check if recipient needs a notification
    sent_notification = await check_recipient_state(
        bot=bot,
        storage=state.storage,
        recipient_telegram_user_id=await user_repo.get_telegram_user_id_by_id(partner.id),
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward message to partner
    await bot.send_message(
        chat_id=await user_repo.get_telegram_user_id_by_id(partner.id),
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
    if not partner:
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
        recipient_telegram_user_id=await user_repo.get_telegram_user_id_by_id(partner.id),
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward photo to partner
    await bot.send_photo(
        chat_id=await user_repo.get_telegram_user_id_by_id(partner.id),
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
    if not partner:
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
        recipient_telegram_user_id=await user_repo.get_telegram_user_id_by_id(partner.id),
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward document to partner
    await bot.send_document(
        chat_id=await user_repo.get_telegram_user_id_by_id(partner.id),
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
    if not partner:
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
        recipient_telegram_user_id=await user_repo.get_telegram_user_id_by_id(partner.id),
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward sticker to partner
    await bot.send_sticker(
        chat_id=await user_repo.get_telegram_user_id_by_id(partner.id),
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
    if not partner:
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
        recipient_telegram_user_id=await user_repo.get_telegram_user_id_by_id(partner.id),
        sender_name=sender_name,
        chat_id=chat_id,
        partner_id=user.id
    )
    
    # Forward voice to partner
    await bot.send_voice(
        chat_id=await user_repo.get_telegram_user_id_by_id(partner.id),
        voice=voice.file_id
    )
