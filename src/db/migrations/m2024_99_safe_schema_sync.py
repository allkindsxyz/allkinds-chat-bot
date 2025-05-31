from sqlalchemy import text

def upgrade(conn):
    # Чаты
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS chats (
            id SERIAL PRIMARY KEY,
            initiator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            ended_at TIMESTAMP
        );
    '''))
    # Добавить group_id если нет
    conn.execute(text('''
        ALTER TABLE chats ADD COLUMN IF NOT EXISTS group_id integer NOT NULL DEFAULT 0;
    '''))
    # Сообщения
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content_type VARCHAR(16) NOT NULL,
            text_content TEXT,
            file_id VARCHAR(255),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            is_read BOOLEAN NOT NULL DEFAULT FALSE
        );
    '''))
    conn.execute(text('''CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id);'''))
    conn.execute(text('''CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_id ON chat_messages(sender_id);'''))
    conn.execute(text('''CREATE INDEX IF NOT EXISTS idx_chat_messages_is_read ON chat_messages(is_read);'''))
    # Блокировки
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            blocked_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, blocked_user_id)
        );
    '''))
    # История раскрытия контактов
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS contact_reveals (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            revealed_at TIMESTAMP NOT NULL DEFAULT NOW(),
            contact_type VARCHAR(32) NOT NULL,
            contact_value VARCHAR(255) NOT NULL
        );
    '''))
    # Никнейм в group_members
    conn.execute(text('''ALTER TABLE group_members ADD COLUMN IF NOT EXISTS nickname VARCHAR(32);'''))

def downgrade(conn):
    # Откат: удаляем только то, что могли создать
    conn.execute(text('''DROP TABLE IF EXISTS contact_reveals;'''))
    conn.execute(text('''DROP TABLE IF EXISTS blocked_users;'''))
    conn.execute(text('''DROP TABLE IF EXISTS chat_messages;'''))
    conn.execute(text('''DROP TABLE IF EXISTS chats;'''))
    conn.execute(text('''ALTER TABLE group_members DROP COLUMN IF EXISTS nickname;''')) 