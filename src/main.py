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

# Check for token with both possible naming conventions
token = os.environ.get("CHAT_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
token_exists = bool(token)
token_length = len(token or "")
token_source = "CHAT_BOT_TOKEN" if os.environ.get("CHAT_BOT_TOKEN") else "BOT_TOKEN" if os.environ.get("BOT_TOKEN") else "none"
logger.info(f"MAIN.PY CHECK: Token availability: exists={token_exists}, length={token_length}, source={token_source}")

# Print all environment variables for Railway debugging (excluding sensitive values)
IS_RAILWAY = os.environ.get("RAILWAY_ENVIRONMENT") is not None
if IS_RAILWAY:
    logger.info("Running in Railway environment, printing environment variables:")
    for key in os.environ:
        if key in ["CHAT_BOT_TOKEN", "BOT_TOKEN", "DATABASE_URL"]:
            logger.info(f"  {key}: [REDACTED]")
        else:
            logger.info(f"  {key}: {os.environ[key]}")

# Add debugging prints to track startup process
logger.info("==== STARTUP TRACKING: Starting import phases ====")

# Import must be done after logging setup
try:
    logger.info("==== STARTUP TRACKING: Importing chat_bot.main ====")
    from src.chat_bot.main import start_chat_bot
    logger.info("==== STARTUP TRACKING: Successfully imported chat_bot.main ====")
    
    logger.info("==== STARTUP TRACKING: Importing core.config ====")
    from src.core.config import get_settings
    logger.info("==== STARTUP TRACKING: Successfully imported core.config ====")
except Exception as e:
    logger.critical(f"==== STARTUP TRACKING: IMPORT ERROR: {e} ====")
    import traceback
    logger.critical(traceback.format_exc())
    sys.exit(1)

logger.info("==== STARTUP TRACKING: All imports successful ====")

def get_webhook_url():
    """Get the webhook URL based on environment variables."""
    try:
        logger.info("==== STARTUP TRACKING: Getting webhook URL ====")
        settings = get_settings()
        
        # In Railway, we use RAILWAY_PUBLIC_DOMAIN
        if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
            host = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
            logger.info(f"Using webhook host from environment: {host}")
            return f"https://{host}/chat_webhook"
        
        # Also try RAILWAY_STATIC_URL as fallback
        if os.environ.get("RAILWAY_STATIC_URL"):
            host = os.environ.get("RAILWAY_STATIC_URL")
            logger.info(f"Using Railway static URL as webhook host: {host}")
            return f"https://{host}/chat_webhook"
        
        # Otherwise use the regular settings
        if settings.use_webhook and settings.webhook_host:
            logger.info(f"Using webhook host from settings: {settings.webhook_host}")
            return f"{settings.webhook_host}{settings.webhook_path}"
        
        return None
    except Exception as e:
        logger.error(f"Error getting webhook URL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def setup_simple_health_check():
    """Setup a simple health check endpoint for Railway."""
    try:
        logger.info("==== STARTUP TRACKING: Setting up health check server ====")
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
        import traceback
        logger.error(traceback.format_exc())
        return None, None

async def main():
    """Main entry point."""
    try:
        logger.info("==== STARTUP TRACKING: Entering main function ====")
        # Set up signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda sig, _: sys.exit(0))
        
        # Print Railway environment variables for debugging
        if IS_RAILWAY:
            for env_var in ["RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL", "PORT"]:
                logger.info(f"  {env_var}: {os.environ.get(env_var)}")
        
        # Get webhook URL
        webhook_url = get_webhook_url()
        logger.info(f"==== STARTUP TRACKING: Webhook URL: {webhook_url} ====")
        
        # Skip setting up health check server since chat bot will handle it
        logger.info("==== STARTUP TRACKING: Skipping separate health check server, webhook server will handle health checks ====")
        
        # Start chat bot
        logger.info("==== STARTUP TRACKING: Starting Chat Bot... ====")
        
        # On Railway, we want to use the webhook configuration
        use_webhook = IS_RAILWAY or os.environ.get("USE_WEBHOOK") == "true" or get_settings().use_webhook
        logger.info(f"==== STARTUP TRACKING: use_webhook: {use_webhook} ====")
        
        # Get token with fallbacks to support both naming conventions
        token = os.environ.get("CHAT_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
        
        if not token:
            logger.critical("No bot token found in environment variables (checked CHAT_BOT_TOKEN and BOT_TOKEN). Cannot start the bot.")
            sys.exit(1)
            
        # Set the token in the environment for the chat bot to find
        os.environ["CHAT_BOT_TOKEN"] = token
        
        logger.info(f"==== STARTUP TRACKING: Starting bot with token (length: {len(token)}) ====")
        try:
            await start_chat_bot(
                token=token,
                use_webhook=use_webhook,
                webhook_url=webhook_url
            )
            logger.info("==== STARTUP TRACKING: Bot started successfully ====")
        except Exception as e:
            logger.critical(f"==== STARTUP TRACKING: Error starting bot: {e} ====")
            import traceback
            logger.critical(traceback.format_exc())
            sys.exit(1)
        
        # Keep the main coroutine running
        logger.info("==== STARTUP TRACKING: Entering main loop ====")
        while True:
            await asyncio.sleep(3600)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

def main_cli():
    """Command line entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 