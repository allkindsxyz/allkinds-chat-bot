import os
import importlib.util
from sqlalchemy import text, create_engine

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL not set")
# Автоматически исправляем префикс для asyncpg
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)
# Для sync engine нужен обычный префикс
if DB_URL.startswith("postgresql+asyncpg://"):
    DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

engine = create_engine(DB_URL, future=True)

MIGRATIONS_PATH = os.path.join(os.path.dirname(__file__), "migrations")

def ensure_migrations_table():
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS applied_migrations (
                name VARCHAR(255) PRIMARY KEY
            )
        '''))

def get_applied_migrations():
    with engine.begin() as conn:
        result = conn.execute(text("SELECT name FROM applied_migrations"))
        return set(row[0] for row in result.fetchall())

def apply_migration(migration_path, migration_name):
    spec = importlib.util.spec_from_file_location(migration_name, migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as conn:
        if hasattr(module, "upgrade"):
            module.upgrade(conn)
        conn.execute(text("INSERT INTO applied_migrations (name) VALUES (:name)"), {"name": migration_name})
        print(f"Applied migration: {migration_name}")

def main():
    ensure_migrations_table()
    applied = get_applied_migrations()
    all_migrations = sorted(f for f in os.listdir(MIGRATIONS_PATH) if f.endswith(".py") and not f.startswith("__"))
    for mig in all_migrations:
        if mig not in applied:
            path = os.path.join(MIGRATIONS_PATH, mig)
            apply_migration(path, mig)

if __name__ == "__main__":
    main() 