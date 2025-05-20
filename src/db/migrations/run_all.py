import os
from sqlalchemy import create_engine

# Получи строку подключения к базе
DATABASE_URL = os.environ.get("DATABASE_URL")

sync_db_url = DATABASE_URL.replace('postgresql+asyncpg', 'postgresql')
engine = create_engine(sync_db_url)

# Список всех миграций по порядку (добавляй новые сюда)
MIGRATIONS = [
    "m2024_01_create_matches_table",
    "m2024_07_chatbot_core_tables",
    "m2024_08_add_telegram_id_to_users",
    "m2024_09_add_username_to_users",
    "m2024_11_add_is_active_to_users",
    "m2024_12_add_is_admin_to_users",
    "m2024_13_add_points_to_users",
    "m2024_14_add_updated_at_to_users",
    "m2024_15_add_bio_to_users"
]

def run_migrations():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            for mig in MIGRATIONS:
                print(f"Applying migration: {mig}")
                mod = __import__(f"src.db.migrations.{mig}", fromlist=["upgrade"])
                mod.upgrade(conn)
            trans.commit()
            print("All migrations applied.")
        except Exception as e:
            trans.rollback()
            print(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    run_migrations() 