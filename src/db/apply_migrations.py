import os
import importlib.util
from sqlalchemy import text, Table, Column, String, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import asyncio

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL not set")

engine = create_async_engine(DB_URL, future=True)

MIGRATIONS_PATH = os.path.join(os.path.dirname(__file__), "migrations")

async def ensure_migrations_table():
    async with engine.begin() as conn:
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS applied_migrations (
                name VARCHAR(255) PRIMARY KEY
            )
        '''))

async def get_applied_migrations():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT name FROM applied_migrations"))
        return set(row[0] for row in result.fetchall())

async def apply_migration(migration_path, migration_name):
    spec = importlib.util.spec_from_file_location(migration_name, migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async with engine.begin() as conn:
        if hasattr(module, "upgrade"):
            await asyncio.get_event_loop().run_in_executor(None, lambda: module.upgrade(conn.sync_connection()))
        await conn.execute(text("INSERT INTO applied_migrations (name) VALUES (:name)"), {"name": migration_name})
        print(f"Applied migration: {migration_name}")

async def main():
    await ensure_migrations_table()
    applied = await get_applied_migrations()
    all_migrations = sorted(f for f in os.listdir(MIGRATIONS_PATH) if f.endswith(".py") and not f.startswith("__"))
    for mig in all_migrations:
        if mig not in applied:
            path = os.path.join(MIGRATIONS_PATH, mig)
            await apply_migration(path, mig)

if __name__ == "__main__":
    asyncio.run(main()) 