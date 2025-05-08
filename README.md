# Allkinds Chat Bot

## Overview
Allkinds Chat Bot is a Telegram bot that enables anonymous communication between users who have been matched based on shared values. This bot is part of the Allkinds service ecosystem, working alongside the main matching bot.

## Features
- Anonymous chat between matched users
- Ability to reveal contact information when both users agree
- Message forwarding with privacy protection
- User blocking functionality
- Connection management

## Technical Stack
- Python 3.9+
- FastAPI
- Aiogram 3.x (Telegram Bot API)
- SQLAlchemy (with PostgreSQL in production, SQLite for development)
- Pydantic for data validation
- Docker support for deployment

## Environment Setup
The bot requires the following environment variables:
```
CHAT_BOT_TOKEN=your_telegram_bot_token
CHAT_BOT_USERNAME=your_bot_username
ADMIN_IDS=comma_separated_admin_ids
DATABASE_URL=your_database_url
```

## Development
```bash
# Install dependencies
poetry install

# Initialize the database
poetry run python -m src.db.init_db

# Run the bot
poetry run python -m src.main
```

## Deployment
The bot can be deployed using Docker:
```bash
docker build -t allkinds-chat-bot .
docker run -d --env-file .env allkinds-chat-bot
```

## Integration
This bot is designed to work with the Allkinds main bot. Users are matched in the main bot and then redirected to this chat bot for anonymous communication. 