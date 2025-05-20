#!/usr/bin/env python3

import asyncio
import sqlite3
import os
import sys
from loguru import logger
from openai import AsyncOpenAI

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import get_settings

settings = get_settings()

# Define our 4 fixed categories
MAIN_CATEGORIES = [
    "🧠 Worldview & Beliefs",
    "❤️ Relationships & Family",
    "🌍 Lifestyle & Society",
    "🎯 Career & Ambitions"
]

client = AsyncOpenAI(api_key=settings.openai_api_key)

async def categorize_to_main_category(question_text: str) -> str:
    """Categorize a question into one of our fixed main categories using OpenAI."""
    try:
        prompt = f"""
        Categorize this question into EXACTLY ONE of these four categories:
        1. 🧠 Worldview & Beliefs (philosophy, values, opinions, religion, politics)
        2. ❤️ Relationships & Family (dating, marriage, children, friends)
        3. 🌍 Lifestyle & Society (hobbies, travel, food, social issues)
        4. 🎯 Career & Ambitions (work, education, goals, money)

        Question: "{question_text}"

        Category (just return the category with emoji, nothing else):
        """
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that categorizes questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=15
        )
        
        category = response.choices[0].message.content.strip()
        
        # Ensure the category is one of our main categories
        for main_cat in MAIN_CATEGORIES:
            if main_cat in category:
                return main_cat
                
        # If OpenAI returns something not in our list, try to map it
        if "world" in category.lower() or "belief" in category.lower() or "opinion" in category.lower():
            return MAIN_CATEGORIES[0]
        elif "relation" in category.lower() or "family" in category.lower() or "love" in category.lower():
            return MAIN_CATEGORIES[1]
        elif "life" in category.lower() or "society" in category.lower() or "hobby" in category.lower():
            return MAIN_CATEGORIES[2]
        elif "career" in category.lower() or "ambit" in category.lower() or "work" in category.lower():
            return MAIN_CATEGORIES[3]
            
        # Default if no mapping found
        logger.warning(f"Could not map category '{category}' - defaulting to {MAIN_CATEGORIES[0]}")
        return MAIN_CATEGORIES[0]
    except Exception as e:
        logger.error(f"Error categorizing question: {e}")
        return MAIN_CATEGORIES[0]  # Default to first category

async def recategorize_all_questions():
    """Recategorize all questions in the database to our fixed categories."""
    # Connect to the SQLite database
    db_path = settings.db_url.replace("sqlite+aiosqlite:///", "")
    if db_path.startswith("./"):
        db_path = db_path[2:]
    
    logger.info(f"Connecting to database at {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch all questions
    cursor.execute("SELECT id, text, category FROM questions")
    questions = cursor.fetchall()
    
    logger.info(f"Found {len(questions)} questions to recategorize")
    
    # Counter for tracking progress
    total = len(questions)
    updated_count = 0
    skipped_count = 0
    
    # Process each question
    for i, (question_id, question_text, current_category) in enumerate(questions):
        # Log progress every 10 questions
        if i % 10 == 0:
            logger.info(f"Processing question {i+1}/{total}")
        
        try:
            # Categorize the question
            new_category = await categorize_to_main_category(question_text)
            
            # Update the database
            cursor.execute(
                "UPDATE questions SET category = ? WHERE id = ?", 
                (new_category, question_id)
            )
            
            logger.info(f"Question {question_id}: '{question_text[:30]}...' recategorized from '{current_category}' to '{new_category}'")
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Failed to recategorize question {question_id}: {e}")
            skipped_count += 1
    
    # Commit the changes
    conn.commit()
    
    # Get category distribution
    cursor.execute("SELECT category, COUNT(*) FROM questions GROUP BY category ORDER BY COUNT(*) DESC")
    category_counts = cursor.fetchall()
    
    logger.info(f"Recategorization complete! Updated {updated_count} questions, skipped {skipped_count}")
    logger.info("Category distribution:")
    for category, count in category_counts:
        logger.info(f"  {category}: {count} questions")
    
    # Close the connection
    conn.close()

if __name__ == "__main__":
    logger.info("Starting question recategorization")
    
    if not settings.openai_api_key:
        logger.error("OpenAI API key not set. Please set the OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    asyncio.run(recategorize_all_questions())
    
    logger.info("Recategorization completed") 