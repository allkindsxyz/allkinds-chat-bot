from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, text
from sqlalchemy.future import select as future_select

from src.db.models.group import Group
from src.db.models.group_member import GroupMember, MemberRole
from src.db.repositories.base import BaseRepository

class GroupRepository(BaseRepository[Group]):
    """Repository for working with Group models."""
    
    def __init__(self):
        super().__init__(Group)
    
    async def get(self, session: AsyncSession, group_id: int) -> Group | None:
        """Get a group by ID."""
        query = select(Group).where(Group.id == group_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def exists(self, session: AsyncSession, group_id: int) -> bool:
        """Check if a group exists by ID."""
        query = select(exists().where(Group.id == group_id))
        result = await session.execute(query)
        return result.scalar_one()
    
    async def create(self, session: AsyncSession, data: dict) -> Group:
        """Create a new group."""
        group = Group(**data)
        session.add(group)
        await session.commit()
        await session.refresh(group)
        return group
        
    async def get_user_groups(self, session: AsyncSession, user_id: int) -> list[Group]:
        """Get all groups a user belongs to (including as creator or member)."""
        # First, get groups where user is creator
        creator_query = select(Group).where(
            Group.creator_user_id == user_id
        )
        creator_result = await session.execute(creator_query)
        creator_groups = creator_result.scalars().all()
        
        # Then, get groups where user is a member
        member_query = select(Group).join(
            GroupMember, Group.id == GroupMember.group_id
        ).where(
            GroupMember.user_id == user_id
        )
        member_result = await session.execute(member_query)
        member_groups = member_result.scalars().all()
        
        # Combine results, removing duplicates
        all_groups = list(set(creator_groups) | set(member_groups))
        return all_groups
        
    async def add_user_to_group(
        self, 
        session: AsyncSession, 
        user_id: int, 
        group_id: int, 
        role: str = MemberRole.MEMBER
    ) -> GroupMember:
        """Add a user as a member of a group."""
        # Check if already a member
        query = select(GroupMember).where(
            (GroupMember.user_id == user_id) & 
            (GroupMember.group_id == group_id)
        )
        result = await session.execute(query)
        existing_membership = result.scalar_one_or_none()
        
        if existing_membership:
            # Already a member, just return existing membership
            return existing_membership
            
        # Create new membership
        membership = GroupMember(
            user_id=user_id,
            group_id=group_id,
            role=role
        )
        session.add(membership)
        await session.commit()
        await session.refresh(membership)
        return membership

    async def get_group_members(self, session: AsyncSession, group_id: int) -> list[GroupMember]:
        """Get all members of a group."""
        query = select(GroupMember).where(GroupMember.group_id == group_id)
        result = await session.execute(query)
        return result.scalars().all()

    async def remove_user_from_group(self, session: AsyncSession, user_id: int, group_id: int) -> bool:
        """Remove a user from a group."""
        query = delete(GroupMember).where(
            GroupMember.user_id == user_id,
            GroupMember.group_id == group_id
        )
        result = await session.execute(query)
        await session.commit()
        return result.rowcount > 0
        
    async def is_user_in_group(self, session: AsyncSession, user_id: int, group_id: int) -> bool:
        """Check if a user is a member of a group."""
        query = select(exists().where(
            (GroupMember.user_id == user_id) & 
            (GroupMember.group_id == group_id)
        ))
        result = await session.execute(query)
        return result.scalar_one()
        
    async def is_group_creator(self, session: AsyncSession, user_id: int, group_id: int) -> bool:
        """Check if a user is the creator of a group."""
        query = select(exists().where(
            (Group.id == group_id) & 
            (Group.creator_user_id == user_id)
        ))
        result = await session.execute(query)
        return result.scalar_one()
        
    async def get_user_role(self, session: AsyncSession, user_id: int, group_id: int) -> str | None:
        """Get the role of a user in a group. Returns None if user is not in group."""
        query = select(GroupMember.role).where(
            (GroupMember.user_id == user_id) & 
            (GroupMember.group_id == group_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_group_member(self, session: AsyncSession, user_id: int, group_id: int) -> GroupMember:
        """Get a group member by user_id and group_id.
        
        Args:
            session: The database session
            user_id: The user ID
            group_id: The group ID
            
        Returns:
            The GroupMember object or None if not found
        """
        try:
            from loguru import logger
            logger.info(f"Fetching group member for user_id={user_id}, group_id={group_id}")
            
            try:
                # Try the full query with all columns
                query = select(GroupMember).where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id
                )
                
                logger.debug(f"Group member query: {str(query)}")
                
                result = await session.execute(query)
                member = result.scalar_one_or_none()
                
                if member:
                    logger.info(f"Found group member: {member}")
                    # Try to access the attributes, handle AttributeError if they don't exist
                    try:
                        nickname = getattr(member, "nickname", None)
                        photo_url = getattr(member, "photo_url", None)
                        logger.info(f"Member attributes: nickname={nickname}, photo_url={photo_url}")
                    except AttributeError as attr_err:
                        logger.warning(f"Some attributes not available on GroupMember: {attr_err}")
                else:
                    logger.warning(f"No group member found for user_id={user_id}, group_id={group_id}")
                    
                return member
                
            except Exception as e:
                # If there's an error about missing columns
                if "column group_members.nickname does not exist" in str(e) or "column group_members.photo_url does not exist" in str(e):
                    logger.warning(f"Database schema missing columns. Using simplified query: {e}")
                    
                    # Try with explicit column selection without the missing ones
                    query = select(
                        GroupMember.id, 
                        GroupMember.group_id, 
                        GroupMember.user_id, 
                        GroupMember.role,
                        GroupMember.joined_at
                    ).where(
                        GroupMember.group_id == group_id,
                        GroupMember.user_id == user_id
                    )
                    
                    result = await session.execute(query)
                    row = result.fetchone()
                    
                    if row:
                        # Create a member object with basic attributes
                        member = GroupMember(
                            id=row[0],
                            group_id=row[1],
                            user_id=row[2],
                            role=row[3],
                            joined_at=row[4]
                        )
                        logger.info(f"Found basic group member: {member}")
                        return member
                    else:
                        logger.warning(f"No group member found for user_id={user_id}, group_id={group_id}")
                        return None
                else:
                    # Re-raise other errors
                    raise
        except Exception as e:
            from loguru import logger
            import traceback
            logger.error(f"Error in get_group_member: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def set_member_profile(self, session: AsyncSession, user_id: int, group_id: int, nickname: str, photo_url: str | None = None) -> GroupMember:
        """Set or update a group member's profile (nickname and photo)."""
        from loguru import logger
        
        # Get the member
        member = await self.get_group_member(session, user_id, group_id)
        
        if not member:
            raise ValueError(f"User {user_id} is not a member of group {group_id}")
        
        try:
            # First try the direct attribute update
            try:
                # Update member profile directly on the object
                member.nickname = nickname
                member.photo_url = photo_url
                
                # Commit the changes
                await session.commit()
                
                # Refresh the member object
                await session.refresh(member)
                logger.info(f"Updated profile for user {user_id} in group {group_id} with nickname '{nickname}'")
                return member
            except Exception as e:
                # Check if it's a missing column error
                if "column group_members.nickname does not exist" in str(e) or "column group_members.photo_url does not exist" in str(e):
                    logger.warning(f"Database schema missing columns. Attempting to migrate: {e}")
                    
                    # Try to add the missing columns
                    try:
                        # Check if we're using SQLite (development) or PostgreSQL (production)
                        from sqlalchemy import text
                        dialect_name = session.bind.dialect.name
                        
                        if dialect_name == 'sqlite':
                            # SQLite migration
                            await session.execute(text("""
                                BEGIN;
                                
                                -- Check if nickname column exists
                                SELECT CASE 
                                    WHEN COUNT(*) = 0 THEN (
                                        ALTER TABLE group_members ADD COLUMN nickname VARCHAR(32)
                                    )
                                END
                                FROM pragma_table_info('group_members') 
                                WHERE name = 'nickname';
                                
                                -- Check if photo_url column exists
                                SELECT CASE 
                                    WHEN COUNT(*) = 0 THEN (
                                        ALTER TABLE group_members ADD COLUMN photo_url VARCHAR(255)
                                    )
                                END
                                FROM pragma_table_info('group_members') 
                                WHERE name = 'photo_url';
                                
                                COMMIT;
                            """))
                            
                        elif dialect_name == 'postgresql':
                            # PostgreSQL migration
                            await session.execute(text("""
                                DO $$
                                BEGIN
                                  -- Add nickname column if it doesn't exist
                                  IF NOT EXISTS(SELECT column_name 
                                               FROM information_schema.columns 
                                               WHERE table_name = 'group_members' AND column_name = 'nickname') THEN
                                    ALTER TABLE group_members ADD COLUMN nickname VARCHAR(32);
                                  END IF;
                                  
                                  -- Add photo_url column if it doesn't exist
                                  IF NOT EXISTS(SELECT column_name 
                                               FROM information_schema.columns 
                                               WHERE table_name = 'group_members' AND column_name = 'photo_url') THEN
                                    ALTER TABLE group_members ADD COLUMN photo_url VARCHAR(255);
                                  END IF;
                                END $$;
                            """))
                            
                        else:
                            # Other databases
                            logger.error(f"Migration not implemented for database dialect: {dialect_name}")
                            return member
                        
                        # Commit the migration
                        await session.commit()
                        logger.info(f"Successfully migrated group_members table to add missing columns")
                        
                        # Now try to update again using SQL directly
                        from sqlalchemy import update
                        stmt = update(GroupMember).where(
                            (GroupMember.user_id == user_id) & 
                            (GroupMember.group_id == group_id)
                        ).values(
                            nickname=nickname,
                            photo_url=photo_url
                        )
                        
                        await session.execute(stmt)
                        await session.commit()
                        
                        # Refresh the member
                        await session.refresh(member)
                        logger.info(f"Updated profile after migration for user {user_id} in group {group_id}")
                        return member
                        
                    except Exception as migration_error:
                        logger.error(f"Migration failed: {migration_error}")
                        # Return the member as is, without nickname/photo
                        return member
                else:
                    # Re-raise other errors
                    raise
        except Exception as e:
            logger.error(f"Error in set_member_profile: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return the member as is
            return member
        
    async def get_member_count(self, session: AsyncSession, group_id: int) -> int:
        """Get the number of members in a group."""
        from sqlalchemy import func
        query = select(func.count()).where(GroupMember.group_id == group_id)
        result = await session.execute(query)
        return result.scalar_one() or 0
        
    async def get_question_count(self, session: AsyncSession, group_id: int) -> int:
        """Get the number of questions in a group."""
        from sqlalchemy import func
        query = select(func.count()).where(Question.group_id == group_id)
        result = await session.execute(query)
        return result.scalar_one() or 0

    async def get_by_invite_code(self, session: AsyncSession, invite_code: str) -> Group | None:
        """Get a group by its invite code."""
        query = select(Group).where(Group.invite_code == invite_code)
        result = await session.execute(query)
        return result.scalar_one_or_none()

# Create a singleton instance
group_repo = GroupRepository() 