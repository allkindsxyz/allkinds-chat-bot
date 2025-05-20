#!/usr/bin/env python3
"""
Health check services for the Allkinds Chat Bot
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
import aiohttp
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/health.log"),
    ]
)
logger = logging.getLogger("health")

# Health check server configuration
CHAT_BOT_PORT = int(os.environ.get("CHAT_BOT_PORT", 8082))
CHAT_BOT_HOST = os.environ.get("CHAT_BOT_HOST", "localhost")

async def check_bot_health(host, port):
    """Check if a bot's health endpoint is responding"""
    try:
        url = f"http://{host}:{port}/health"
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "ok",
                        "details": data,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Received status code {response.status}",
                        "timestamp": datetime.now().isoformat()
                    }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }

async def health_handler(request):
    """Aggregate health check endpoint"""
    chat_status = await check_bot_health(CHAT_BOT_HOST, CHAT_BOT_PORT)
    
    # Aggregate status
    overall_status = "ok" if chat_status["status"] == "ok" else "degraded"
    
    result = {
        "status": overall_status,
        "services": {
            "chat_bot": chat_status,
        },
        "timestamp": datetime.now().isoformat()
    }
    
    status_code = 200 if overall_status == "ok" else 503
    return web.json_response(result, status=status_code)

async def start_health_server():
    """Start the health check server"""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    
    port = int(os.environ.get("HEALTH_PORT", 8080))
    logger.info(f"Starting health check server on port {port}")
    logger.info(f"Chat bot expected at {CHAT_BOT_HOST}:{CHAT_BOT_PORT}")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    return site, runner

async def main():
    """Main entry point for the health check server"""
    try:
        site, runner = await start_health_server()
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
            
    except KeyboardInterrupt:
        logger.info("Shutting down health check server...")
    except Exception as e:
        logger.error(f"Error in health check server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
