import os
import sys
import sqlite3
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "allkinds.db")

# Category consolidation mapping
# Maps specific categories to broader categories
CATEGORY_MAPPING = {
    # Sports & Physical Activity
    "🏀 SPORTS": "🏀 Sports & Activities",
    "🥅 SPORTS": "🏀 Sports & Activities",
    "🎱 SPORTS": "🏀 Sports & Activities",
    "🏄‍♂️ WATERSPORTS": "🏀 Sports & Activities",
    "🏃‍♂️ FITNESS": "🏀 Sports & Activities",
    "🏃‍♂️ EXERCISE": "🏀 Sports & Activities",
    "💪 FITNESS": "🏀 Sports & Activities",
    
    # Travel & Outdoors
    "🌍 TRAVEL": "✈️ Travel & Outdoors",
    "🌎 TRAVEL": "✈️ Travel & Outdoors",
    "🌴TRAVEL": "✈️ Travel & Outdoors",
    "🏔️ TRAVEL": "✈️ Travel & Outdoors", 
    "🚶‍♂️ OUTDOORS": "✈️ Travel & Outdoors",
    "🎣 OUTDOORS": "✈️ Travel & Outdoors",
    "🏆 EXPLORATION": "✈️ Travel & Outdoors",
    
    # Lifestyle & Hobbies
    "🧘‍♂️ WELLNESS": "🎵 Lifestyle & Hobbies",
    "🎵 MUSIC": "🎵 Lifestyle & Hobbies",
    "🥦 VEGETARIANISM": "🎵 Lifestyle & Hobbies",
    "🚬 SMOKING": "🎵 Lifestyle & Hobbies", 
    "🍴 FOOD PREFERENCES": "🎵 Lifestyle & Hobbies",
    "📚 LITERATURE": "🎵 Lifestyle & Hobbies",
    "🎉 HOBBIES": "🎵 Lifestyle & Hobbies",
    "🎄 HOLIDAYS": "🎵 Lifestyle & Hobbies",
    
    # Family & Relationships
    "👶 FAMILY": "👪 Family & Relationships",
    "💑 FAMILY RELATIONS": "👪 Family & Relationships",
    "💬 PARENTING": "👪 Family & Relationships",
    "👀 DATING": "👪 Family & Relationships",
    "🐶 PETS": "👪 Family & Relationships",
    
    # Personal Information & Identity
    "💬 PERSONAL INFORMATION": "🧠 Personal Identity",
    "👤 IDENTITY": "🧠 Personal Identity",
    "🤔 EXISTENTIALISM": "🧠 Personal Identity",
    "🤔 ETHICS": "🧠 Personal Identity",
    
    # Media & Technology 
    "📱 SOCIAL MEDIA": "📱 Media & Technology",
    "🤖 TECHNOLOGY": "📱 Media & Technology",
    "📰 NEWS": "📱 Media & Technology",
    
    # Languages & Communication
    "🗣️ LANGUAGE": "🗣️ Language & Communication",
    
    # Beliefs & Values
    "🕍 RELIGION": "🌍 Beliefs & Values",
    "🗳️ POLITICS": "🌍 Beliefs & Values",
    "🏳️‍🌈 LGBTQ+": "🌍 Beliefs & Values",
    "🤔 INQUIRY": "🌍 Beliefs & Values"
}

def consolidate_categories():
    """Consolidate many specific categories into broader categories."""
    logger.info(f"Using database at: {DB_PATH}")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all questions with their current categories
        cursor.execute("SELECT id, text, category FROM questions")
        questions = cursor.fetchall()
        
        logger.info(f"Found {len(questions)} questions to process")
        
        if not questions:
            logger.info("No questions to process")
            return
        
        # Display original category distribution
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM questions 
            GROUP BY category 
            ORDER BY count DESC
        """)
        original_categories = cursor.fetchall()
        
        print("\nOriginal category distribution:")
        print("-------------------------------")
        for category, count in original_categories:
            category_display = category if category else "Uncategorized"
            print(f"{category_display}: {count} questions")
        
        # Process each question
        updated_count = 0
        skipped_count = 0
        category_updates = {}
        
        for question_id, question_text, current_category in questions:
            # Skip questions without categories
            if not current_category:
                skipped_count += 1
                continue
                
            # Look up mapped category
            uppercase_category = current_category.upper()
            mapped_category = CATEGORY_MAPPING.get(uppercase_category)
            
            # If a mapping exists, update the question
            if mapped_category and mapped_category != current_category:
                cursor.execute(
                    "UPDATE questions SET category = ? WHERE id = ?",
                    (mapped_category, question_id)
                )
                
                category_updates[current_category] = mapped_category
                updated_count += 1
                logger.info(f"Updated question {question_id}: '{current_category}' -> '{mapped_category}'")
        
        # Commit changes
        conn.commit()
        
        # Display mapping applied
        print("\nCategory mapping applied:")
        print("-----------------------")
        for original, new in category_updates.items():
            print(f"{original} -> {new}")
        
        # Display updated category distribution
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM questions 
            GROUP BY category 
            ORDER BY count DESC
        """)
        new_categories = cursor.fetchall()
        
        print("\nUpdated category distribution:")
        print("-----------------------------")
        for category, count in new_categories:
            category_display = category if category else "Uncategorized"
            print(f"{category_display}: {count} questions")
        
        print(f"\nSummary: {updated_count} questions updated, {skipped_count} skipped, {len(questions) - updated_count - skipped_count} unchanged")
        
        logger.info(f"Category consolidation completed: {updated_count} questions updated")
        conn.close()
    except Exception as e:
        logger.error(f"Consolidation failed: {e}")
        raise

if __name__ == "__main__":
    consolidate_categories() 