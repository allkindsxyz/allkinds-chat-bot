import os
import sys
import sqlite3
from loguru import logger

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allkinds.db")

def check_categories():
    """Check what categories currently exist in the questions table."""
    logger.info(f"Using database at: {DB_PATH}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all distinct categories
        cursor.execute("SELECT DISTINCT category FROM questions")
        categories = cursor.fetchall()
        
        # Get count per category
        logger.info(f"Found {len(categories)} unique categories")
        print("\nCategories in database:")
        print("----------------------")
        
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM questions 
            GROUP BY category 
            ORDER BY count DESC
        """)
        category_counts = cursor.fetchall()
        
        for category, count in category_counts:
            category_display = category if category else "NULL"
            print(f"{category_display}: {count} questions")
        
        conn.close()
    except Exception as e:
        logger.error(f"Failed to check categories: {e}")
        raise

if __name__ == "__main__":
    check_categories() 