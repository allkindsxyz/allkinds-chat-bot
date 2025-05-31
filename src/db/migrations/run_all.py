import os
from sqlalchemy import create_engine

# Получи строку подключения к базе
DATABASE_URL = os.environ.get("DATABASE_URL")

sync_db_url = DATABASE_URL.replace('postgresql+asyncpg', 'postgresql')
engine = create_engine(sync_db_url)

# Список всех миграций по порядку (добавляй новые сюда)
MIGRATIONS = [
    "m2024_01_create_matches_table",
    "m2024_02_add_group_id_to_matches",
    "m2024_07_chatbot_core_tables",
    "m2024_03_add_updated_at_to_chats",
    "m2024_09_add_username_to_users",
    "m2024_11_add_is_active_to_users",
    "m2024_12_add_is_admin_to_users",
    "m2024_13_add_points_to_users",
    "m2024_14_add_updated_at_to_users",
    "m2024_15_add_bio_to_users",
    "m2024_99_safe_schema_sync",
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
    try:
        run_migrations()
    except Exception as e:
        print(f"Standard migration sequence failed: {e}")
        print("Attempting to run safe schema sync migration directly...")
        # Явно вызываем safe schema sync миграцию, даже если были ошибки выше
        from sqlalchemy import create_engine
        DATABASE_URL = os.environ.get("DATABASE_URL")
        sync_db_url = DATABASE_URL.replace('postgresql+asyncpg', 'postgresql')
        engine = create_engine(sync_db_url)
        with engine.connect() as conn:
            import importlib.util
            import os
            path = os.path.join(os.path.dirname(__file__), "m2024_99_safe_schema_sync.py")
            spec = importlib.util.spec_from_file_location("m2024_99_safe_schema_sync", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.upgrade(conn)
        print("Safe schema sync migration applied.") 