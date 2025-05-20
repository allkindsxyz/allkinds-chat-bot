"""
Add group_id column to chats table
"""
from sqlalchemy import text

def upgrade(conn):
    conn.execute(text('ALTER TABLE chats ADD COLUMN group_id integer NOT NULL DEFAULT 0;'))

def downgrade(conn):
    conn.execute(text('ALTER TABLE chats DROP COLUMN group_id;')) 