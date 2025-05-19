from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
    """))

def downgrade(conn):
    conn.execute(text("""
        ALTER TABLE users DROP COLUMN IF EXISTS is_active;
    """)) 