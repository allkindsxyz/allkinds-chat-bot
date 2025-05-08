from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Chat


async def get_chat_by_participants(session: AsyncSession, user1_id: int, user2_id: int, group_id: int) -> Chat:
    """
    Get a chat by its participants (regardless of who is initiator or recipient).
    
    Args:
        session: Database session
        user1_id: ID of the first participant
        user2_id: ID of the second participant
        group_id: ID of the group
        
    Returns:
        Chat object if found, None otherwise
    """
    # Check both directions of initiator/recipient
    query = select(Chat).where(
        and_(
            Chat.group_id == group_id,
            ((Chat.initiator_id == user1_id) & (Chat.recipient_id == user2_id)) |
            ((Chat.initiator_id == user2_id) & (Chat.recipient_id == user1_id))
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none() 