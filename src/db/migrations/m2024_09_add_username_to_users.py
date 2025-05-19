from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(64);
    """))

def downgrade(conn):
    conn.execute(text("""
        ALTER TABLE users DROP COLUMN IF EXISTS username;
    """)) 