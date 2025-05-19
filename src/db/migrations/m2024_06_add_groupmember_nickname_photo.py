from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE group_members ADD COLUMN IF NOT EXISTS nickname VARCHAR(32);
    """))

def downgrade(conn):
    conn.execute(text("""
        ALTER TABLE group_members DROP COLUMN IF EXISTS nickname;
    """)) 