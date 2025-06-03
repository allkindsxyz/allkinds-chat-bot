from aiogram import types
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List, Optional


def get_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """Creates the main menu keyboard with options to select chat and manage users."""
    builder = ReplyKeyboardBuilder()
    
    # First row - select chat partner
    builder.row(
        types.KeyboardButton(text="👥 Select user to chat")
    )
    
    # Second row - manage users
    builder.row(
        types.KeyboardButton(text="⚙️ Manage users")
    )
    
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_back_to_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """Creates a keyboard with a back to menu button."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="🔙 Back to menu")
    )
    
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_in_chat_keyboard(partner_name: str) -> types.ReplyKeyboardMarkup:
    """Creates a keyboard for when a user is in a chat."""
    builder = ReplyKeyboardBuilder()
    
    # First row - What's Next button with partner name
    builder.row(
        types.KeyboardButton(text=f"🙌 What's next with {partner_name}?")
    )
    
    # Second row - Switch chat button
    builder.row(
        types.KeyboardButton(text="👥 Switch chat")
    )
    
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def get_chat_selection_keyboard(
    users: List[dict],
    page: int = 0,
    page_size: int = 5
) -> types.InlineKeyboardMarkup:
    """
    Creates a keyboard with users to select for chatting.
    
    Args:
        users: List of user dicts with fields: id, name, unread_count, chat_id, latest_message
        page: Current page number (0-based)
        page_size: Number of users per page
        
    Returns:
        Inline keyboard with user buttons and pagination
    """
    builder = InlineKeyboardBuilder()
    
    # Calculate pagination
    total_pages = (len(users) + page_size - 1) // page_size if users else 1
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(users))
    
    # Add user buttons
    for i in range(start_idx, end_idx):
        user = users[i]
        unread_badge = f" 🔴({user['unread_count']})" if user.get('unread_count', 0) > 0 else ""
        
        # Include chat_id in callback data
        chat_id = user.get('chat_id', 0)
        
        # Create button for user
        builder.row(types.InlineKeyboardButton(
            text=f"{user['name']}{unread_badge}",
            callback_data=f"chat:{user['id']}:{chat_id}"
        ))
    
    # Add pagination if needed
    pagination_row = []
    if total_pages > 1:
        if page > 0:
            pagination_row.append(types.InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"page:{page-1}"
            ))
        
        # Current page indicator
        pagination_row.append(types.InlineKeyboardButton(
            text=f"📄 {page+1}/{total_pages}",
            callback_data="noop"
        ))
        
        if page < total_pages - 1:
            pagination_row.append(types.InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"page:{page+1}"
            ))
    
    # Add pagination row if it has buttons
    if pagination_row:
        builder.row(*pagination_row)
    
    return builder.as_markup()


def get_user_management_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Creates a keyboard for managing a chat partner."""
    builder = InlineKeyboardBuilder()
    
    # Action buttons
    builder.row(types.InlineKeyboardButton(
        text="👤 Show Username",
        callback_data=f"show_username:{user_id}"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text="🗑 Delete Match & Chat",
        callback_data=f"delete_match:{user_id}"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text="⛔ Block User",
        callback_data=f"block_user:{user_id}"
    ))
    
    # Back button
    builder.row(types.InlineKeyboardButton(
        text="🔙 Back",
        callback_data="back_to_menu"
    ))
    
    return builder.as_markup()


def get_select_user_to_manage_keyboard(
    users: List[dict],
    page: int = 0,
    page_size: int = 5
) -> types.InlineKeyboardMarkup:
    """
    Creates a keyboard with users to select for management.
    
    Args:
        users: List of user dicts with fields: id, name
        page: Current page number (0-based)
        page_size: Number of users per page
        
    Returns:
        Inline keyboard with user buttons and pagination
    """
    builder = InlineKeyboardBuilder()
    
    # Calculate pagination
    total_pages = (len(users) + page_size - 1) // page_size if users else 1
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(users))
    
    # Add user buttons
    for i in range(start_idx, end_idx):
        user = users[i]
        builder.button(
            text=f"⚙️ {user['name']}",
            callback_data=f"manage:{user['id']}"
        )
    
    # Add pagination if needed
    pagination_row = []
    if total_pages > 1:
        if page > 0:
            pagination_row.append(types.InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"manage_page:{page-1}"
            ))
        
        # Current page indicator
        pagination_row.append(types.InlineKeyboardButton(
            text=f"📄 {page+1}/{total_pages}",
            callback_data="noop"
        ))
        
        if page < total_pages - 1:
            pagination_row.append(types.InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"manage_page:{page+1}"
            ))
    
    # Add pagination row if it has buttons
    if pagination_row:
        builder.row(*pagination_row)
    
    # Add back button
    builder.row(types.InlineKeyboardButton(
        text="🔙 Back",
        callback_data="back_to_menu"
    ))
    
    return builder.as_markup()


def get_confirm_delete_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Creates a keyboard for confirming deletion of a match."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Yes, delete",
            callback_data=f"confirm_delete:{user_id}"
        ),
        types.InlineKeyboardButton(
            text="❌ No, cancel",
            callback_data=f"manage:{user_id}"
        )
    )
    
    return builder.as_markup()


def get_confirm_block_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Creates a keyboard for confirming blocking a user."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Yes, block",
            callback_data=f"confirm_block:{user_id}"
        ),
        types.InlineKeyboardButton(
            text="❌ No, cancel",
            callback_data=f"manage:{user_id}"
        )
    )
    
    return builder.as_markup()


def get_chat_history_keyboard(
    chat_id: int, 
    current_offset: int = 0,
    has_more: bool = True
) -> types.InlineKeyboardMarkup:
    """
    Creates a keyboard for chat history navigation.
    
    Args:
        chat_id: ID of the chat session
        current_offset: Current offset (how many messages already loaded)
        has_more: Whether there are more messages to load
        
    Returns:
        Inline keyboard with Load More button if there are more messages
    """
    builder = InlineKeyboardBuilder()
    
    if has_more:
        builder.button(
            text="📜 Load more messages",
            callback_data=f"load_more:{chat_id}:{current_offset+20}"
        )
    
    return builder.as_markup()


def get_whats_next_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Creates a keyboard with options for what to do next in a chat."""
    builder = InlineKeyboardBuilder()
    
    # Options for what to do next
    builder.row(types.InlineKeyboardButton(
        text="💬 Keep Chatting",
        callback_data=f"next_keep_chatting:{user_id}"
    ))
    builder.row(types.InlineKeyboardButton(
        text="🤖 AI Analysis",
        callback_data=f"ai_analysis:{user_id}"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text="👤 Share my Telegram account",
        callback_data=f"next_connect_directly:{user_id}"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text="🗑️ Delete Chat",
        callback_data=f"delete_match:{user_id}"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text="⛔ Block User",
        callback_data=f"block_user:{user_id}"
    ))
    
    return builder.as_markup() 