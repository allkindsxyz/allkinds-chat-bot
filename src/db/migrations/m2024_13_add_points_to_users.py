from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS points INTEGER DEFAULT 0;
    """))

def downgrade(conn):
    conn.execute(text("""
        ALTER TABLE users DROP COLUMN IF EXISTS points;
    """)) 