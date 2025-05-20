from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE matches ADD COLUMN IF NOT EXISTS group_id INTEGER;
    """))

def downgrade(conn):
    conn.execute(text("""
        ALTER TABLE matches DROP COLUMN IF EXISTS group_id;
    """))