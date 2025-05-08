#!/usr/bin/env python3
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger
import asyncio
import os
import signal
import sys
import aiohttp
import ssl
from dotenv import load_dotenv
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from typing import Any, Awaitable, Callable, Dict
from datetime import datetime
import threading
from aiohttp import web
from aiogram import types
import json

from src.chat_bot.handlers import register_handlers
from src.core.config import get_settings
from src.chat_bot.middlewares import DatabaseMiddleware, LoggingMiddleware, BotMiddleware

# Set up logging to a specific file for debugging
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"logs/chat_bot_debug_{current_time}.log"
logger.remove()  # Remove default handlers
logger.add(log_file, rotation="20 MB", level="DEBUG", backtrace=True, diagnose=True)
logger.add(sys.stderr, level="INFO")
logger.info(f"Chat bot logs will be written to {log_file}")

# Load env variables directly from .env file
load_dotenv()

# Try to get token from environment directly first, then fallback to settings
CHAT_BOT_TOKEN = os.environ.get("CHAT_BOT_TOKEN")
if not CHAT_BOT_TOKEN:
    # Fallback to settings
    settings = get_settings()
    CHAT_BOT_TOKEN = settings.CHAT_BOT_TOKEN
    logger.info("Token loaded from settings")
else:
    logger.info("Token loaded directly from environment")

# Log token first few characters for debugging
if CHAT_BOT_TOKEN:
    logger.info("Token loaded successfully")
else:
    logger.error("No token found!")

# Global variables for clean shutdown
bot = None
dp = None
should_exit = False

async def reset_webhook():
    """Reset the Telegram webhook to ensure no conflicts."""
    if not CHAT_BOT_TOKEN:
        logger.error("Cannot reset webhook: No token available")
        return False
    # Try with direct HTTP request as fallback
    try:
        logger.info("Trying reset webhook with direct HTTP request as fallback...")
        import requests
        response = requests.get(
            f"https://api.telegram.org/bot{CHAT_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true",
            verify=False,
            timeout=10
        )
        result = response.json()
        if result.get("ok"):
            logger.info("Webhook deleted successfully with direct HTTP request")
            return True
        else:
            logger.error(f"Failed to delete webhook: {result}")
            return False
    except Exception as e:
        logger.error(f"Error with direct webhook reset: {e}")
        return False
    
    # Try with aiohttp client
    try:
        logger.info("Resetting Telegram webhook using aiohttp...")
        # Create a default SSL context that doesn't verify
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create a session with relaxed SSL configuration
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            # First, check current webhook status
            async with session.get(
                f"https://api.telegram.org/bot{CHAT_BOT_TOKEN}/getWebhookInfo"
            ) as response:
                webhook_info = await response.json()
                logger.info(f"Current webhook status: {webhook_info}")
            
            # Force delete the webhook with drop_pending_updates
            async with session.get(
                f"https://api.telegram.org/bot{CHAT_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
            ) as response:
                result = await response.json()
                if result.get("ok"):
                    logger.info("Webhook deleted successfully")
                    return True
                else:
                    logger.error(f"Failed to delete webhook: {result}")
                    
            # Verify webhook was deleted
            await asyncio.sleep(1)  # Give Telegram a moment to process
            async with session.get(
                f"https://api.telegram.org/bot{CHAT_BOT_TOKEN}/getWebhookInfo"
            ) as response:
                webhook_info = await response.json()
                if webhook_info.get("ok") and not webhook_info.get("result", {}).get("url"):
                    logger.info("Verified webhook is now empty")
                    return True
    except Exception as e:
        logger.error(f"Error resetting webhook: {e}")
    
    return False

async def setup_webhook_server():
    """Set up a web server for webhooks and health checks."""
    try:
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"Setting up chat webhook server on port {port}")
        
        app = web.Application()
        
        async def ping_handler(request):
            """Simple ping handler for health checks."""
            return web.Response(text='{"status":"ok","service":"chat_bot"}', 
                               content_type='application/json')
                               
        async def health_handler(request):
            """Health check handler for Railway."""
            return web.Response(text='{"status":"ok","service":"allkinds-chat-bot","version":"1.0.0"}', 
                               content_type='application/json')
                               
        async def webhook_handler(request):
            """Handle webhook updates from Telegram."""
            try:
                logger.info(f"[WEBHOOK] Received request from {request.remote}")
                
                if request.content_type != 'application/json':
                    logger.warning(f"[WEBHOOK] Invalid content type: {request.content_type}")
                    return web.Response(status=415, text='Only JSON is accepted')
                    
                try:
                    data = await request.read()
                    logger.info(f"[WEBHOOK] Received webhook update: {len(data)} bytes")
                    
                    # Log message text if available for debugging
                    try:
                        update_json = json.loads(data)
                        logger.info(f"[WEBHOOK] Update JSON: {update_json}")
                        
                        # Check for message and handle critical commands directly if processing fails
                        if "message" in update_json and "text" in update_json["message"]:
                            text = update_json["message"]["text"]
                            logger.info(f"[WEBHOOK] Message text: {text}")
                            user_id = update_json["message"].get("from", {}).get("id")
                            
                            # Try main processing path
                            try:
                                # Process update with the bot
                                update = types.Update.model_validate_json(data)
                                await dp.feed_update(bot=bot, update=update)
                                logger.info(f"[WEBHOOK] Successfully processed update through dispatcher")
                                return web.Response(text='{"ok":true}', content_type='application/json')
                            except Exception as e:
                                # Main processing failed, try emergency direct response for critical commands
                                logger.error(f"[WEBHOOK] Error in main processing: {e}")
                                import traceback
                                logger.error(f"[WEBHOOK] Traceback: {traceback.format_exc()}")
                                
                                # For critical commands, send direct response
                                if text == "/start":
                                    logger.info(f"[WEBHOOK] Direct handling for /start command")
                                    try:
                                        await bot.send_message(
                                            chat_id=user_id,
                                            text="Welcome to the Allkinds Chat Bot! 👋\n\n"
                                                "This bot lets you chat anonymously with your matches.\n\n"
                                                "To get started, find a match in @AllkindsTeamBot."
                                        )
                                        logger.info(f"[WEBHOOK] Direct response sent for /start")
                                    except Exception as direct_error:
                                        logger.error(f"[WEBHOOK] Even direct response failed: {direct_error}")
                                
                                elif text == "/help":
                                    logger.info(f"[WEBHOOK] Direct handling for /help command")
                                    try:
                                        await bot.send_message(
                                            chat_id=user_id,
                                            text="Need help? This bot lets you chat anonymously with your matches from the Allkinds main bot.",
                                            parse_mode="HTML"
                                        )
                                        logger.info(f"[WEBHOOK] Direct response sent for /help")
                                    except Exception as direct_error:
                                        logger.error(f"[WEBHOOK] Even direct response failed: {direct_error}")
                        else:
                            # No text command to handle as fallback, try normal processing
                            update = types.Update.model_validate_json(data)
                            await dp.feed_update(bot=bot, update=update)
                            logger.info(f"[WEBHOOK] Successfully processed non-message update")
                    except Exception as json_error:
                        logger.error(f"[WEBHOOK] Error parsing JSON: {json_error}")
                        # Try main processing anyway
                        update = types.Update.model_validate_json(data)
                        await dp.feed_update(bot=bot, update=update)
                    
                    return web.Response(text='{"ok":true}', content_type='application/json')
                except Exception as e:
                    logger.error(f"[WEBHOOK] Error processing webhook update: {e}")
                    import traceback
                    logger.error(f"[WEBHOOK] Traceback: {traceback.format_exc()}")
                    return web.Response(text='{"ok":false,"error":"Internal Server Error"}', 
                                       content_type='application/json', status=500)
            except Exception as outer_e:
                logger.error(f"[WEBHOOK] Outer exception in webhook handler: {outer_e}")
                import traceback
                logger.error(f"[WEBHOOK] Outer traceback: {traceback.format_exc()}")
                return web.Response(text='{"ok":false,"error":"Internal Server Error"}', 
                                   content_type='application/json', status=500)
        
        async def root_handler(request):
            """Root path handler for diagnostics."""
            return web.Response(text="Allkinds chat Bot is running. Use the Telegram app to interact with the bot.")
        
        # Add routes
        app.router.add_get("/ping", ping_handler)
        app.router.add_get("/health", health_handler)
        app.router.add_get("/", root_handler)
        app.router.add_post("/chat_webhook", webhook_handler)
        
        # Add a simple diagnostic test route
        async def test_route_handler(request):
            """Simple test route to check if the server is responding."""
            logger.info(f"[TEST_ROUTE] Test route accessed from {request.remote}")
            return web.Response(text=json.dumps({
                "status": "ok",
                "server": "allkinds-chat-bot",
                "time": str(datetime.now()),
                "webhook_path": webhook_path,
                "webhook_url": f"{webhook_host}{webhook_path}" if webhook_host else "not_set"
            }), content_type='application/json')
            
        app.router.add_get("/test", test_route_handler)
        
        # Add database test route
        async def db_test_handler(request):
            """Test database connectivity."""
            logger.info(f"[DB_TEST] Database test accessed from {request.remote}")
            result = {"status": "unknown", "details": {}}
            
            try:
                # Import database modules
                from sqlalchemy import text
                from src.db.base import get_async_engine, get_async_session
                
                # Test database connectivity with basic query
                try:
                    engine = get_async_engine()
                    result["details"]["engine_created"] = True
                    
                    # Try to create a session
                    session_maker = get_async_session()
                    result["details"]["session_maker_created"] = True
                    
                    # Try a simple query
                    async with session_maker() as session:
                        query_result = await session.execute(text("SELECT 1"))
                        test_value = query_result.scalar()
                        result["details"]["query_executed"] = True
                        result["details"]["query_result"] = test_value
                        
                    # Overall status
                    result["status"] = "ok"
                    logger.info("[DB_TEST] Database connection successful")
                    
                except Exception as db_error:
                    logger.error(f"[DB_TEST] Database connectivity error: {db_error}")
                    result["status"] = "error"
                    result["error"] = str(db_error)
                    result["details"]["error_type"] = type(db_error).__name__
                    
                    # Get additional error info
                    import traceback
                    result["details"]["traceback"] = traceback.format_exc()
            except Exception as outer_error:
                logger.error(f"[DB_TEST] Outer error in database test: {outer_error}")
                result["status"] = "error"
                result["error"] = str(outer_error)
                
            return web.Response(text=json.dumps(result, default=str), 
                               content_type='application/json')
        
        app.router.add_get("/db_test", db_test_handler)
        
        # Log all routes for debugging
        logger.info("Registered routes:")
        for route in app.router.routes():
            logger.info(f"  {route.method} {route.resource.canonical}")
        
        # Start the server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        
        logger.info(f"Webhook server running on http://0.0.0.0:{port}")
        
        # Configure webhook URL
        # Get webhook details from environment
        webhook_host = os.environ.get("WEBHOOK_HOST")
        webhook_path = os.environ.get("CHAT_BOT_WEBHOOK_PATH", "/chat_webhook")
        
        # Construct full webhook URL
        if webhook_host:
            # Make sure webhook host has https:// prefix
            if not webhook_host.startswith("http"):
                webhook_host = f"https://{webhook_host}"
                
            webhook_url = f"{webhook_host}{webhook_path}"
            logger.info(f"Setting webhook URL: {webhook_url}")
            
            try:
                # First, check current webhook setting
                webhook_info = await bot.get_webhook_info()
                logger.info(f"Current webhook info: url={webhook_info.url}, pending_update_count={webhook_info.pending_update_count}")
                
                # Set the webhook
                await bot.set_webhook(webhook_url)
                logger.info("Webhook set successfully")
                
                # Verify webhook was set correctly
                webhook_info = await bot.get_webhook_info()
                logger.info(f"Verified webhook info after setting: url={webhook_info.url}, pending_update_count={webhook_info.pending_update_count}")
                
                if webhook_info.url != webhook_url:
                    logger.error(f"Webhook verification failed! Expected {webhook_url}, got {webhook_info.url}")
                else:
                    logger.info("Webhook verification successful")
                    
                # Check for last error
                if webhook_info.last_error_date:
                    logger.error(f"Webhook has error: {webhook_info.last_error_message} at {webhook_info.last_error_date}")
                
            except Exception as e:
                logger.error(f"Failed to set webhook: {e}")
                import traceback
                logger.error(f"Webhook setup traceback: {traceback.format_exc()}")
                
                # Try an alternate method to set webhook directly with requests
                try:
                    logger.info("Trying alternate webhook setup method...")
                    import requests
                    set_webhook_url = f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}"
                    response = requests.get(set_webhook_url, verify=False)
                    logger.info(f"Alternate webhook setup result: {response.status_code} {response.text}")
                except Exception as alt_e:
                    logger.error(f"Alternate webhook setup failed: {alt_e}")
        else:
            logger.warning("No webhook host set, skipping webhook configuration")
        
        # Keep running until signal to exit
        while not should_exit:
            await asyncio.sleep(1)
            
        # Cleanup
        logger.info("Shutting down webhook server")
        await runner.cleanup()
    except Exception as e:
        logger.error(f"Error setting up webhook server: {e}")

async def shutdown(signal_name=None):
    """Shutdown the bot gracefully."""
    global bot, should_exit
    
    if signal_name:
        logger.info(f"Received {signal_name}, shutting down...")
    
    # Set the exit flag for health server
    should_exit = True
    
    # Close bot session properly
    if bot:
        logger.info("Closing bot connection...")
        await bot.session.close()
    
    logger.info("chat bot stopped.")

async def start_chat_bot(token=None, use_webhook=False, webhook_url=None) -> None:
    """Initialize and start the chat bot."""
    global bot, dp, should_exit
    
    try:
        # Use token from parameter or environment
        if not token:
            token = os.environ.get("CHAT_BOT_TOKEN")
            if not token:
                logger.error("No token provided to start_chat_bot and CHAT_BOT_TOKEN env var not found")
                raise ValueError("Telegram bot token is required")

        # Validate token format
        if not token or not token.strip() or len(token) < 20:
            logger.error(f"Invalid token format. Token length: {len(token) if token else 0}")
            raise ValueError("Invalid token format")
            
        logger.info("Initializing bot with valid token...")

        # Reset webhook before starting
        if not await reset_webhook():
            logger.warning("Could not reset webhook completely, will try one more time...")
            # Wait a bit and try one more time
            await asyncio.sleep(5)
            if not await reset_webhook():
                logger.error("Failed to reset webhook after multiple attempts, this may cause conflicts!")

        logger.info("Creating bot instance with token...")
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        # Verify token by getting bot info
        try:
            # Check for bot username in environment
            bot_username = os.environ.get("CHAT_BOT_USERNAME", "")
            if not bot_username:
                from src.core.config import get_settings
                settings = get_settings()
                bot_username = settings.CHAT_BOT_USERNAME
                logger.info(f"Using bot username from settings: {bot_username}")
            else:
                logger.info(f"Using bot username from environment: {bot_username}")

            # Remove @ if it's included
            if bot_username and bot_username.startswith("@"):
                bot_username = bot_username[1:]
                logger.info(f"Removed @ prefix from bot username")
                
            bot_info = await bot.get_me()
            logger.info(f"Bot verification successful: @{bot_info.username}")
        except Exception as e:
            logger.error(f"Bot verification failed: {e}")
            
            # Log detailed error for debugging
            import traceback
            logger.error(f"Bot verification traceback: {traceback.format_exc()}")
            raise ValueError(f"Token is invalid!")

        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Register middlewares
        dp.update.middleware(BotMiddleware(bot))
        dp.update.middleware(DatabaseMiddleware())
        dp.update.middleware(LoggingMiddleware())

        register_handlers(dp)

        # Decide on webhook vs polling mode
        if use_webhook and webhook_url:
            logger.info(f"Starting chat bot in webhook mode with URL: {webhook_url}")
            await setup_webhook_server()
        else:
            logger.info("Starting chat bot in polling mode...")
            # Start polling
            try:
                logger.info("Bot started polling for updates")
                await dp.start_polling(bot, skip_updates=True)
            except asyncio.CancelledError:
                logger.info("Bot polling cancelled")
            except Exception as e:
                logger.error(f"Error during polling: {e}")
                logger.exception("Full traceback:")
                if use_webhook:
                    logger.info("Falling back to webhook mode...")
                    await setup_webhook_server()
                
    except Exception as e:
        logger.exception(f"Error starting chat bot: {e}")
        raise
    finally:
        # Only shutdown if an exception was raised
        if sys.exc_info()[0] is not None:
            await shutdown()

def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    for sig_name in ('SIGINT', 'SIGTERM'):
        asyncio.get_event_loop().add_signal_handler(
            getattr(signal, sig_name),
            lambda sig_name=sig_name: asyncio.create_task(shutdown(sig_name))
        )

if __name__ == '__main__':
    # Setup signal handlers
    setup_signal_handlers()
    
    try:
        asyncio.run(start_chat_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by keyboard interrupt")
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}") 