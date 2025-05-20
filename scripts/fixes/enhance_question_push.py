#!/usr/bin/env python3
"""
Enhancement script to implement direct question pushing on group join/onboarding.

This script modifies the process_group_photo function to directly push
questions to users when they complete the onboarding process.
"""
import os
import re
import shutil
import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def backup_file(target_file):
    """Create a backup of the target file before modifying it."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{target_file}.bak_{timestamp}"
    shutil.copy2(target_file, backup_file)
    logger.info(f"Created backup at {backup_file}")
    return backup_file

def fix_process_group_photo(target_file):
    """Enhance the process_group_photo function to directly push questions."""
    if not os.path.exists(target_file):
        logger.error(f"Target file {target_file} does not exist.")
        return False
    
    with open(target_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Find the target section in the process_group_photo function
    target_pattern = r'(if unanswered_count > 0:[^\n]*\n\s+await message\.answer\([^)]*\)\n\s+)(\# Display the first question[^\n]*\n\s+await check_and_display_next_question\(message, db_user, group_id, state, session\))'
    match = re.search(target_pattern, content)
    
    if not match:
        logger.error("Could not find the target section in process_group_photo function.")
        return False
    
    # Replace with the enhanced implementation
    enhanced_section = """# ENHANCED: Always display the first question after onboarding
                try:
                    # Get the next question directly from repository
                    from src.db.repositories.question import QuestionRepository
                    question_repo_direct = QuestionRepository()
                    
                    next_question = await question_repo_direct.get_next_question_for_user(
                        session=session,
                        user_id=db_user.id,
                        group_id=group_id,
                        excluded_ids=[],
                        get_latest=True  # Get newest questions first
                    )
                    
                    if next_question:
                        logger.info(f"Found question {next_question.id} to push to user {user_tg.id} after onboarding")
                        
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                        
                        # Create answer keyboard
                        answer_keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton("⛔ Strong No", callback_data=f"answer:{next_question.id}:strong_no"),
                                    InlineKeyboardButton("❌ No", callback_data=f"answer:{next_question.id}:no")
                                ],
                                [
                                    InlineKeyboardButton("✅ Yes", callback_data=f"answer:{next_question.id}:yes"),
                                    InlineKeyboardButton("💯 Strong Yes", callback_data=f"answer:{next_question.id}:strong_yes")
                                ]
                            ]
                        )
                        
                        # Format question
                        question_author = "Anonymous"
                        if hasattr(next_question, 'user') and next_question.user:
                            if next_question.user.username:
                                question_author = f"@{next_question.user.username}"
                            elif next_question.user.first_name:
                                question_author = next_question.user.first_name
                        
                        question_text = f"❓ {next_question.text}\\n\\nAsked by: {question_author}"
                        await message.answer(question_text, reply_markup=answer_keyboard)
                        logger.info(f"Successfully pushed question {next_question.id} to user {user_tg.id} after onboarding")
                    else:
                        # Fallback to regular display if direct push fails
                        await check_and_display_next_question(message, db_user, group_id, state, session)
                except Exception as q_error:
                    logger.error(f"Error pushing question directly: {q_error}", exc_info=True)
                    # Fallback to regular question display"""
    
    # Replace the old code with the enhanced section
    modified_content = content.replace(match.group(2), enhanced_section)
    
    # Write back to the file
    with open(target_file, 'w', encoding='utf-8') as file:
        file.write(modified_content)
    
    logger.info(f"Enhanced process_group_photo function in {target_file}")
    return True

def main():
    target_file = "src/bot/handlers/start.py"
    
    # Create a backup of the original file
    backup_file(target_file)
    
    # Fix the process_group_photo function
    if fix_process_group_photo(target_file):
        logger.info("Successfully enhanced process_group_photo function to push questions after onboarding.")
        return True
    else:
        logger.error("Failed to enhance process_group_photo function.")
        return False

if __name__ == "__main__":
    main() 