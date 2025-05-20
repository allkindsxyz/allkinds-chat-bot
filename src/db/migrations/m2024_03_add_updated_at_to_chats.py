from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE chats ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;
    """))

def downgrade(conn):
    conn.execute(text("""
        ALTER TABLE chats DROP COLUMN IF EXISTS updated_at;
    """)) 