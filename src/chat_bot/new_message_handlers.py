"""
Message handling functionality for the chat bot.
"""
from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey, BaseStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from src.db.models import AnonymousChatSession, Chat
from src.db.repositories.user import user_repo
from src.db.repositories.chat_message_repo import chat_message_repo
from src.chat_bot.chat_handlers import get_chat_by_id

from .states import ChatState
from .keyboards import get_in_chat_keyboard
from .repositories import get_partner_nickname


async def check_recipient_state(
    bot: Bot, 
    storage: BaseStorage,
    recipient_telegram_user_id: int,
    sender_name: str,
    chat_id: int,
    partner_id: int,
    is_group_chat: bool = False,
    session_id: str = None,
    group_id: int = None,
    match_id: int = None
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
        is_group_chat: Whether this is a group chat
        session_id: Session ID (for anonymous chats)
        group_id: Group ID (for group chats)
        match_id: Match ID (for anonymous chats)
        
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
                "partner_id": partner_id,
                "is_group_chat": is_group_chat
            }
            
            # Add type-specific data
            if is_group_chat:
                open_chat_data["group_id"] = group_id
            else:
                open_chat_data["session_id"] = session_id
                open_chat_data["match_id"] = match_id
            
            # Create inline keyboard with button to open chat
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📨 Open Chat",
                            callback_data=f"open_chat:{partner_id}:{chat_id}:{'true' if is_group_chat else 'false'}"
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
                                callback_data=f"open_chat:{partner_id}:{chat_id}:{'true' if is_group_chat else 'false'}"
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

# Handle messages in chat
@router.message(ChatState.in_chat, F.text)
async def relay_message(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Relay messages between paired users."""
    user_id = message.from_user.id
    user = await user_repo.get_by_telegram_user_id(session, user_id)
    
    if not user:
        await message.answer("You need to register in the main bot first.")
        return
    
    data = await state.get_data()
    
    # Check if this is a group chat (Chat model) or anonymous chat (AnonymousChatSession model)
    is_group_chat = data.get("is_group_chat", False)
    partner_id = data.get("partner_id")
    
    if not partner_id:
        await message.answer("You are not connected to anyone. Select a chat first.")
        await state.clear()
        return
    
    if is_group_chat:
        chat_id = data.get("chat_id")
        group_id = data.get("group_id")
        # Get chat from Chat model
        chat = await get_chat_by_id(session, chat_id)
        
        if not chat or chat.status != "active":
            await message.answer("This chat is no longer active.")
            await state.clear()
            return
            
        # No need to save message for group chat, just forward it
        partner = await user_repo.get(session, partner_id)
        if not partner or not partner.telegram_user_id:
            await message.answer("Cannot find your chat partner. They may have left.")
            return
        
        # Get sender's name for notification
        sender_name = await get_partner_nickname(session, user.id, group_id)
        
        # Forward the message to partner
        try:
            # First check if recipient needs a notification
            sent_notification = await check_recipient_state(
                bot=bot,
                storage=state.storage,
                recipient_telegram_user_id=partner.telegram_user_id,
                sender_name=sender_name,
                chat_id=chat_id,
                partner_id=user.id,
                is_group_chat=True,
                group_id=group_id
            )
            
            # Always send the message even if notification was sent
            await bot.send_message(
                chat_id=partner.telegram_user_id,
                text=message.text
            )
            
        except Exception as e:
            logger.error(f"Error forwarding message in group chat: {e}")
            await message.answer("Failed to send your message. The recipient may have blocked the bot.")
    else:
        # This is an anonymous chat session
        chat_id = data.get("chat_id")
        session_id = data.get("session_id")
        match_id = data.get("match_id")
        
        if not chat_id:
            await message.answer("You are not connected to anyone. Select a chat first.")
            await state.clear()
            return
        
        # Get chat session
        chat_session = await get_chat_by_id(session, chat_id)
        if not chat_session or chat_session.status != "active":
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
                formatted_message = f"[{timestamp}] You: {message.text}\n\n"
                
                # Get current history message
                try:
                    history_message = await bot.get_message(chat_id=user_id, message_id=history_message_id)
                    
                    # Check if message is too long for Telegram's limit
                    if len(history_message.text + formatted_message) > 4000:
                        # If too long, send a notification that history is now in multiple messages
                        await message.answer(
                            "Chat history is now split across multiple messages. "
                            "Return to the menu and select this chat again to see full history."
                        )
                    else:
                        # Add new message to history and update
                        current_text = history_message.text
                        # Find title and preserve it
                        title_end = current_text.find("\n\n")
                        if title_end != -1:
                            title = current_text[:title_end + 2]  # Include the newlines
                            current_content = current_text[title_end + 2:]
                            new_content = formatted_message + current_content
                            await bot.edit_message_text(
                                chat_id=user_id,
                                message_id=history_message_id,
                                text=title + new_content,
                                parse_mode="HTML",
                                reply_markup=history_message.reply_markup
                            )
                except Exception as e:
                    logger.error(f"Error updating history message: {e}")
                    # Continue anyway, this is not critical
            except Exception as e:
                logger.error(f"Error handling history update: {e}")
        
        # Forward the message to partner
        try:
            # First check if recipient needs a notification
            sent_notification = await check_recipient_state(
                bot=bot,
                storage=state.storage,
                recipient_telegram_user_id=partner.telegram_user_id,
                sender_name=sender_name,
                chat_id=chat_id,
                partner_id=user.id,
                is_group_chat=False,
                session_id=session_id,
                match_id=match_id
            )
            
            if not sent_notification:
                # They're already in chat with this user, update their chat history too
                partner_state_key = StorageKey(bot_id=bot.id, user_id=partner.telegram_user_id, chat_id=partner.telegram_user_id)
                partner_data = await state.storage.get_data(key=partner_state_key)
                partner_history_id = partner_data.get("history_message_id")
                
                if partner_history_id:
                    try:
                        # Format message for partner's view
                        timestamp = new_message.created_at.strftime("%H:%M")
                        partner_formatted_msg = f"[{timestamp}] {sender_name}: {message.text}\n\n"
                        
                        # Get current history message
                        try:
                            partner_history = await bot.get_message(
                                chat_id=partner.telegram_user_id, 
                                message_id=partner_history_id
                            )
                            
                            # Check if message is too long
                            if len(partner_history.text + partner_formatted_msg) > 4000:
                                # Too long, don't update
                                pass
                            else:
                                # Add new message to history and update
                                current_text = partner_history.text
                                # Find title and preserve it
                                title_end = current_text.find("\n\n")
                                if title_end != -1:
                                    title = current_text[:title_end + 2]  # Include the newlines
                                    current_content = current_text[title_end + 2:]
                                    new_content = partner_formatted_msg + current_content
                                    await bot.edit_message_text(
                                        chat_id=partner.telegram_user_id,
                                        message_id=partner_history_id,
                                        text=title + new_content,
                                        parse_mode="HTML",
                                        reply_markup=partner_history.reply_markup
                                    )
                        except Exception as e:
                            logger.error(f"Error updating partner history: {e}")
                    except Exception as e:
                        logger.error(f"Error handling partner history update: {e}")
            
            # Always send the message even if notification was sent
            await bot.send_message(
                chat_id=partner.telegram_user_id,
                text=message.text
            )
            
        except Exception as e:
            logger.error(f"Error forwarding message to partner: {e}")
            await message.answer("Failed to send your message. The recipient may have blocked the bot.") 