import asyncio
import os
import sys
import sqlite3
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the new categorization function
from src.core.question_categorizer import categorize_question

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allkinds.db")

async def update_categories():
    """Update all existing questions with new custom categories."""
    logger.info(f"Using database at: {DB_PATH}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all questions
        cursor.execute("SELECT id, text, category FROM questions ORDER BY id")
        questions = cursor.fetchall()
        
        logger.info(f"Found {len(questions)} questions to re-categorize")
        
        if not questions:
            logger.info("No questions to update")
            return
        
        print("\nUpdating question categories...")
        print("--------------------------")
        
        # Track categorization statistics
        updated = 0
        unchanged = 0
        categories_assigned = {}
        
        # Process each question
        for question_id, question_text, old_category in questions:
            print(f"Question {question_id}: {question_text[:50]}...", end='', flush=True)
            
            try:
                # Get new category
                new_category = await categorize_question(question_text)
                
                # Update database only if category changed
                if new_category != old_category:
                    cursor.execute("UPDATE questions SET category = ? WHERE id = ?", (new_category, question_id))
                    conn.commit()
                    updated += 1
                    print(f" {old_category} -> {new_category}")
                else:
                    unchanged += 1
                    print(f" (unchanged: {old_category})")
                
                # Track statistics
                categories_assigned[new_category] = categories_assigned.get(new_category, 0) + 1
                
            except Exception as e:
                print(f" -> ERROR: {str(e)}")
                logger.error(f"Failed to update category for question {question_id}: {e}")
            
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.2)
        
        # Print summary
        print("\nCategory update results:")
        print("----------------------")
        print(f"Total questions processed: {len(questions)}")
        print(f"Categories updated: {updated}")
        print(f"Categories unchanged: {unchanged}")
        
        if categories_assigned:
            print("\nNew category distribution:")
            for category, count in sorted(categories_assigned.items(), key=lambda x: x[1], reverse=True):
                print(f"  {category}: {count}")
        
        logger.info("Category update completed")
        conn.close()
    except Exception as e:
        logger.error(f"Update failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(update_categories()) 