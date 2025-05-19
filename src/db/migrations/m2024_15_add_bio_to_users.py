from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS bio VARCHAR(500);
    """))

def downgrade(conn):
    conn.execute(text("""
        ALTER TABLE users DROP COLUMN IF EXISTS bio;
    """)) 