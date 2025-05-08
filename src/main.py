#!/usr/bin/env python3
"""
Main entry point for Allkinds Chat Bot
"""

import asyncio
import logging
import sys
import os
import signal
from loguru import logger
from dotenv import load_dotenv

# Configure logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/chat_bot_{time}.log", rotation="10 MB", level="DEBUG")

# Force load .env and override any existing OS env vars from it for this process
if load_dotenv(override=True, verbose=True):
    logger.info(".env file loaded successfully in main.py")
else:
    logger.warning(".env file NOT loaded by explicit call in main.py, or it was empty.")

# Always log the token's availability (but not the token itself)
token_exists = bool(os.environ.get("CHAT_BOT_TOKEN"))
token_length = len(os.environ.get("CHAT_BOT_TOKEN", "")) if token_exists else 0
logger.info(f"MAIN.PY CHECK: CHAT_BOT_TOKEN availability: exists={token_exists}, length={token_length}")

# Print all environment variables for Railway debugging (excluding sensitive values)
IS_RAILWAY = os.environ.get("RAILWAY_ENVIRONMENT") is not None
if IS_RAILWAY:
    logger.info("Running in Railway environment, printing environment variables:")
    for key in os.environ:
        if key in ["CHAT_BOT_TOKEN", "DATABASE_URL"]:
            logger.info(f"  {key}: [REDACTED]")
        else:
            logger.info(f"  {key}: {os.environ[key]}")

# Import must be done after logging setup
from src.chat_bot.main import start_chat_bot
from src.core.config import get_settings

def get_webhook_url():
    """Get the webhook URL based on environment variables."""
    try:
        settings = get_settings()
        
        # In Railway, we use RAILWAY_PUBLIC_DOMAIN
        if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
            host = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
            logger.info(f"Using webhook host from environment: {host}")
            return f"https://{host}/webhook"
        
        # Otherwise use the regular settings
        if settings.use_webhook and settings.webhook_host:
            logger.info(f"Using webhook host from settings: {settings.webhook_host}")
            return f"{settings.webhook_host}{settings.webhook_path}"
        
        return None
    except Exception as e:
        logger.error(f"Error getting webhook URL: {e}")
        return None

async def setup_simple_health_check():
    """Setup a simple health check endpoint for Railway."""
    try:
        from aiohttp import web
        
        async def health_handler(request):
            return web.json_response({
                "status": "ok",
                "service": "allkinds-chat-bot",
                "version": "1.0.0"
            })
        
        app = web.Application()
        app.router.add_get('/health', health_handler)
        
        port = int(os.environ.get("PORT", 8080))
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"Health check server running on port {port}")
        return site, runner
    except Exception as e:
        logger.error(f"Failed to start health check server: {e}")
        return None, None

async def main():
    """Main entry point."""
    try:
        # Set up signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda sig, _: sys.exit(0))
        
        # Print Railway environment variables for debugging
        if IS_RAILWAY:
            for env_var in ["RAILWAY_PUBLIC_DOMAIN", "PORT"]:
                logger.info(f"  {env_var}: {os.environ.get(env_var)}")
        
        # Get webhook URL
        webhook_url = get_webhook_url()
        
        # Start health check server (for Railway)
        health_check = await setup_simple_health_check()
        
        # Start chat bot
        logger.info("Starting Chat Bot...")
        
        # On Railway, we want to use the webhook configuration
        use_webhook = IS_RAILWAY or os.environ.get("USE_WEBHOOK") == "true" or get_settings().use_webhook
        
        # Set up the token one more time, just in case it wasn't loaded properly earlier
        if "CHAT_BOT_TOKEN" not in os.environ and os.path.exists(".env"):
            logger.warning("CHAT_BOT_TOKEN not found in environment, trying to load from .env again")
            load_dotenv(override=True)
        
        token = os.environ.get("CHAT_BOT_TOKEN")
        if not token:
            logger.critical("CHAT_BOT_TOKEN environment variable is not set. Cannot start the bot.")
            sys.exit(1)
            
        await start_chat_bot(
            token=token,
            use_webhook=use_webhook,
            webhook_url=webhook_url
        )
        
        # Keep the main coroutine running
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)

def main_cli():
    """Command line entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 