#!/usr/bin/env python3

import asyncio
import sys
import os
from loguru import logger
from openai import AsyncOpenAI
import psycopg2
from psycopg2.extras import DictCursor

# Add the project root to the Python path to import src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.core.credentials import get_database_url, get_api_credentials

# Define our 4 fixed categories
MAIN_CATEGORIES = [
    "🧠 Worldview & Beliefs",
    "❤️ Relationships & Family",
    "🌍 Lifestyle & Society",
    "🎯 Career & Ambitions"
]

# Get credentials using the secure credentials module
DB_URL = get_database_url()
openai_creds = get_api_credentials("openai")
OPENAI_API_KEY = openai_creds["api_key"]

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

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

async def recategorize_railway_questions():
    """Recategorize all questions in the Railway PostgreSQL database to our fixed categories."""
    try:
        # Connect to the PostgreSQL database
        logger.info(f"Connecting to database...")
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = False
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        # Check connection
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        logger.info(f"Database connection test: {result}")
        
        # First check current category distribution
        cursor.execute("SELECT category, COUNT(*) FROM questions GROUP BY category ORDER BY COUNT(*) DESC")
        category_counts = cursor.fetchall()
        
        logger.info("Current category distribution:")
        for row in category_counts:
            category = row["category"] if row["category"] else "None"
            count = row["count"]
            logger.info(f"  {category}: {count} questions")
        
        # Fetch all questions
        cursor.execute("SELECT id, text, category FROM questions")
        questions = cursor.fetchall()
        
        logger.info(f"Found {len(questions)} questions to recategorize")
        
        # Counter for tracking progress
        total = len(questions)
        updated_count = 0
        skipped_count = 0
        
        # Process each question
        for i, row in enumerate(questions):
            question_id = row['id']
            question_text = row['text']
            current_category = row['category'] if row['category'] else "None"
            
            # Log progress every 10 questions
            if i % 10 == 0:
                logger.info(f"Processing question {i+1}/{total}")
            
            try:
                # Categorize the question
                new_category = await categorize_to_main_category(question_text)
                
                # Update the database
                cursor.execute(
                    "UPDATE questions SET category = %s WHERE id = %s", 
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
        logger.info("New category distribution:")
        for row in category_counts:
            category = row["category"] if row["category"] else "None"
            count = row["count"]
            logger.info(f"  {category}: {count} questions")
        
        # Close the connection
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")

if __name__ == "__main__":
    logger.info("Starting question recategorization")
    asyncio.run(recategorize_railway_questions())
    logger.info("Recategorization completed") 