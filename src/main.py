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

# Import must be done after logging setup
from src.chat_bot.main import start_chat_bot
from src.core.config import get_settings

# Force load .env and override any existing OS env vars from it for this process
if load_dotenv(override=True, verbose=True):
    logger.info(".env file loaded successfully by explicit call in main.py")
else:
    logger.warning(".env file NOT loaded by explicit call in main.py, or it was empty.")

import os # ensure os is imported after dotenv load for this check
logger.info(f"MAIN.PY CHECK: CHAT_BOT_TOKEN from os.environ: {os.environ.get('CHAT_BOT_TOKEN')}")

# Signal handler for graceful shutdown
async def shutdown(signal_name=None):
    """Shutdown the chat bot gracefully."""
    if signal_name:
        logger.info(f"Received {signal_name}, shutting down...")
    
    # Perform any cleanup here
    logger.info("Shutting down...")
    
    # Exit the process
    asyncio.get_event_loop().stop()

def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    for sig_name in ('SIGINT', 'SIGTERM'):
        asyncio.get_event_loop().add_signal_handler(
            getattr(signal, sig_name),
            lambda sig_name=sig_name: asyncio.create_task(shutdown(sig_name))
        )

def get_webhook_url():
    """Get the webhook URL from environment or settings."""
    # Try to get from environment first
    webhook_host = os.environ.get("WEBHOOK_HOST")
    if not webhook_host:
        # Try Railway's static URL
        railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if railway_url:
            webhook_host = f"https://{railway_url}"
            logger.info(f"Using Railway public domain: {webhook_host}")
        else:
            # Fallback to settings
            settings = get_settings()
            webhook_host = settings.WEBHOOK_HOST
            logger.info(f"Using webhook host from settings: {webhook_host}")
    else:
        logger.info(f"Using webhook host from environment: {webhook_host}")
    
    return webhook_host
    
async def setup_simple_health_check(port=8080):
    """Set up a simple health check endpoint."""
    from aiohttp import web
    
    app = web.Application()
    
    async def health_handler(request):
        """Simple health check endpoint."""
        return web.Response(text='{"status":"ok","service":"chat_bot"}',
                          content_type='application/json')
                          
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    logger.info(f"Health check server running on port {port}")
    
    try:
        # Keep the task running
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Health check server task cancelled")
        await runner.cleanup()

async def main():
    """Main entry point for the chat bot."""
    # Setup signal handlers
    setup_signal_handlers()
    
    # Log environment variables (safely)
    logger.info("Checking environment variables:")
    env_vars = {
        "CHAT_BOT_TOKEN": bool(os.environ.get("CHAT_BOT_TOKEN")),
        "CHAT_BOT_USERNAME": os.environ.get("CHAT_BOT_USERNAME", "Not set"),
        "WEBHOOK_HOST": os.environ.get("WEBHOOK_HOST", "Not set"),
        "RAILWAY_PUBLIC_DOMAIN": os.environ.get("RAILWAY_PUBLIC_DOMAIN", "Not set"),
        "RAILWAY_ENVIRONMENT": os.environ.get("RAILWAY_ENVIRONMENT", "Not set"),
        "PORT": os.environ.get("PORT", "Not set")
    }
    for var, value in env_vars.items():
        if isinstance(value, bool):
            logger.info(f"  {var}: {'Set' if value else 'Not set'}")
        else:
            logger.info(f"  {var}: {value}")
            
    # Get webhook URL for Railway
    webhook_url = get_webhook_url()
    logger.info(f"Webhook URL: {webhook_url}")
    
    # Set environment variables for children processes
    # Force polling mode
    os.environ["USE_WEBHOOK"] = "false"
    os.environ["WEBHOOK_PATH"] = "/webhook"
    
    # Start health check in a separate task
    health_port = int(os.environ.get("PORT", 8080))
    health_task = asyncio.create_task(setup_simple_health_check(health_port))
    logger.info(f"Started health check on port {health_port}")
    
    try:
        # Start the chat bot in a separate task
        logger.info("Starting Chat Bot...")
        chat_bot_task = asyncio.create_task(start_chat_bot())
        
        # Wait for chat bot task to complete
        await chat_bot_task
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
    finally:
        logger.info("Initiating shutdown sequence...")

        # Cancel bot task
        if 'chat_bot_task' in locals() and not chat_bot_task.done():
            logger.info("Cancelling chat_bot_task...")
            chat_bot_task.cancel()

        # Wait for bot task to finish cleanup (with a timeout)
        if 'chat_bot_task' in locals():
            logger.info("Waiting for chat bot task to complete cancellation...")
            try:
                await asyncio.wait(
                    [chat_bot_task],
                    timeout=10.0  # Adjust timeout as needed
                )
                logger.info("Chat bot task completed cancellation.")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for chat bot task to cancel.")
            except Exception as ex:
                logger.error(f"Exception during chat bot task cancellation wait: {ex}")
        
        # Cancel health check task
        if 'health_task' in locals() and not health_task.done():
            logger.info("Cancelling health_task...")
            health_task.cancel()
            try:
                await health_task
                logger.info("Health_task cancelled.")
            except asyncio.CancelledError:
                logger.info("Health_task confirmed cancelled.")
            except Exception as ex:
                logger.error(f"Exception during health_task cancellation: {ex}")
        
        logger.info("Chat bot shutdown sequence complete.")

if __name__ == "__main__":
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Chat bot stopped by keyboard interrupt")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1) 