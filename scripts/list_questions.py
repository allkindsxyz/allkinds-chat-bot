import os
import sqlite3
from loguru import logger

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allkinds.db")

def list_questions():
    """List all questions with their categories."""
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all questions with their categories
        cursor.execute("""
            SELECT id, text, category 
            FROM questions 
            ORDER BY id
        """)
        questions = cursor.fetchall()
        
        print(f"\nTotal questions: {len(questions)}")
        print("----------------------------------------")
        
        # Display questions grouped by category
        print("\nQUESTIONS BY CATEGORY:")
        print("======================")
        
        # Get questions grouped by category
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM questions 
            GROUP BY category 
            ORDER BY count DESC
        """)
        categories = cursor.fetchall()
        
        for category, count in categories:
            category_display = category if category else "Uncategorized"
            print(f"\n{category_display.upper()} ({count} questions):")
            print("-" * (len(category_display) + 14))
            
            cursor.execute("""
                SELECT id, text 
                FROM questions 
                WHERE category = ? 
                ORDER BY id
            """, (category,))
            
            category_questions = cursor.fetchall()
            for q_id, text in category_questions:
                print(f"{q_id}. {text}")
        
        conn.close()
    except Exception as e:
        logger.error(f"Failed to list questions: {e}")
        raise

if __name__ == "__main__":
    list_questions() 