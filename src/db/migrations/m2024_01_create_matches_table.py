from sqlalchemy import text

def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            user1_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            user2_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            score FLOAT DEFAULT 0.0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """))

def downgrade(conn):
    conn.execute(text("""
        DROP TABLE IF EXISTS matches;
    """)) 