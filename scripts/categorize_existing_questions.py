import asyncio
import os
import sys
import sqlite3
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the categorization function from the new module
from src.core.question_categorizer import categorize_question

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allkinds.db")

async def categorize_existing_questions():
    """Dynamically categorize all existing questions using OpenAI."""
    logger.info(f"Using database at: {DB_PATH}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all questions
        cursor.execute("SELECT id, text FROM questions")
        questions = cursor.fetchall()
        
        logger.info(f"Found {len(questions)} questions to categorize")
        
        if not questions:
            logger.info("No questions to categorize")
            return
        
        print("\nProcessing questions:")
        print("--------------------")
        
        # Track categorization statistics
        successful = 0
        failed = 0
        categories_assigned = {}
        
        # Process each question
        for question_id, question_text in questions:
            print(f"Question {question_id}: {question_text[:50]}...", end='', flush=True)
            
            try:
                # Get dynamic category from OpenAI
                category = await categorize_question(question_text)
                
                # Update the database
                cursor.execute("UPDATE questions SET category = ? WHERE id = ?", (category, question_id))
                conn.commit()
                
                # Track statistics
                successful += 1
                categories_assigned[category] = categories_assigned.get(category, 0) + 1
                
                print(f" -> {category}")
                logger.info(f"Categorized question {question_id} as '{category}'")
            except Exception as e:
                failed += 1
                print(f" -> ERROR: {str(e)}")
                logger.error(f"Failed to categorize question {question_id}: {e}")
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        # Print summary
        print("\nCategorization results:")
        print("----------------------")
        print(f"Total questions processed: {len(questions)}")
        print(f"Successfully categorized: {successful}")
        print(f"Failed to categorize: {failed}")
        
        if categories_assigned:
            print("\nCategories assigned:")
            for category, count in sorted(categories_assigned.items(), key=lambda x: x[1], reverse=True):
                print(f"  {category}: {count}")
        
        logger.info("Categorization completed")
        conn.close()
    except Exception as e:
        logger.error(f"Categorization failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(categorize_existing_questions()) 