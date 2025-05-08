#!/usr/bin/env python3
"""
Health check endpoint for Railway deployment.
Also provides webhook forwarding to ensure bots receive commands.
"""

import os
import logging
import sys
import json
import time
import asyncio
from http import HTTPStatus

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service configuration
MAIN_BOT_PORT = int(os.environ.get("MAIN_BOT_PORT", 8081))
chat_BOT_PORT = int(os.environ.get("chat_BOT_PORT", 8082))
MAIN_BOT_HOST = os.environ.get("MAIN_BOT_HOST", "localhost")
chat_BOT_HOST = os.environ.get("chat_BOT_HOST", "localhost")

try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse
    import httpx
    
    # Create FastAPI app
    app = FastAPI(title="Allkinds Service")

    @app.get("/health")
    async def health_check():
        """Health check endpoint for Railway."""
        # Check if bots are accessible
        bot_status = {
            "main_bot": await check_bot_health(MAIN_BOT_HOST, MAIN_BOT_PORT),
            "chat_bot": await check_bot_health(chat_BOT_HOST, chat_BOT_PORT)
        }
        
        return {
            "status": "ok",
            "service": "allkinds",
            "environment": os.environ.get("RAILWAY_ENVIRONMENT", "unknown"),
            "bots": bot_status,
            "version": "1.1.0",
            "webhook_host": os.environ.get("WEBHOOK_HOST", "not_set")
        }

    @app.get("/")
    async def root():
        """Root endpoint redirects to health check."""
        return await health_check()
    
    async def check_bot_health(host, port):
        """Check if a bot service is running and responding."""
        try:
            url = f"http://{host}:{port}/ping"
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, timeout=2.0)
                    if response.status_code == 200:
                        return "running"
                    return f"error: status {response.status_code}"
                except Exception as e:
                    return f"error: {str(e)}"
        except Exception as e:
            return f"error: {str(e)}"
        
    @app.post("/webhook")
    async def webhook_handler(request: Request):
        """Unified webhook handler that forwards to the appropriate bot."""
        try:
            body = await request.body()
            try:
                update = json.loads(body)
                update_id = update.get("update_id", "unknown")
                logger.info(f"Received update ID: {update_id}")
                
                # Log message text if available
                if "message" in update and "text" in update["message"]:
                    logger.info(f"Message text: {update['message']['text']}")
            except Exception as e:
                logger.error(f"Error parsing update: {e}")
            
            # Forward the update to both bots internally
            async with httpx.AsyncClient() as client:
                # Forward to main bot
                main_url = f"http://{MAIN_BOT_HOST}:{MAIN_BOT_PORT}/webhook"
                logger.info(f"Forwarding to main bot: {main_url}")
                try:
                    main_response = await client.post(
                        main_url, 
                        content=body,
                        timeout=5.0
                    )
                    logger.info(f"Main bot response: {main_response.status_code}")
                except Exception as e:
                    logger.error(f"Error forwarding to main bot: {e}")
                
                # Forward to chat bot
                comm_url = f"http://{chat_BOT_HOST}:{chat_BOT_PORT}/webhook"
                logger.info(f"Forwarding to chat bot: {comm_url}")
                try:
                    comm_response = await client.post(
                        comm_url, 
                        content=body,
                        timeout=5.0
                    )
                    logger.info(f"chat bot response: {comm_response.status_code}")
                except Exception as e:
                    logger.error(f"Error forwarding to chat bot: {e}")
            
            return Response(status_code=HTTPStatus.OK)
        except Exception as e:
            logger.exception(f"Error in webhook handler: {e}")
            return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    
    @app.get("/ping")
    async def ping():
        """Simple ping endpoint for health checks."""
        return {"status": "ok"}

    async def wait_for_bots_startup():
        """Wait for bots to start up before accepting webhooks."""
        logger.info("Waiting for bots to start up...")
        max_attempts = 20
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Checking bot services (attempt {attempt}/{max_attempts})...")
            main_status = await check_bot_health(MAIN_BOT_HOST, MAIN_BOT_PORT)
            comm_status = await check_bot_health(chat_BOT_HOST, chat_BOT_PORT)
            
            if "running" in main_status and "running" in comm_status:
                logger.info("Both bots are running!")
                return True
                
            if attempt < max_attempts:
                logger.info(f"Waiting for bots... Main: {main_status}, chat: {comm_status}")
                await asyncio.sleep(5)
        
        logger.warning("Timed out waiting for bots to start. Continuing anyway.")
        return False

    if __name__ == "__main__":
        try:
            import uvicorn
            port = int(os.environ.get("PORT", 8080))
            logger.info(f"Starting Allkinds service on port {port}")
            logger.info(f"Main bot expected at {MAIN_BOT_HOST}:{MAIN_BOT_PORT}")
            logger.info(f"chat bot expected at {chat_BOT_HOST}:{chat_BOT_PORT}")
            
            # Start background task to check bot status
            asyncio.run(wait_for_bots_startup())
            
            uvicorn.run(app, host="0.0.0.0", port=port)
        except ImportError:
            logger.error("Uvicorn not installed. Falling back to simple HTTP server.")
            from http.server import HTTPServer, BaseHTTPRequestHandler
            
            class SimpleHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok","service":"allkinds"}')
                
                def do_POST(self):
                    if self.path == '/webhook':
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(b'{"ok":true}')
                        logger.info("Webhook request received but can't be processed in simple mode")
            
            port = int(os.environ.get("PORT", 8080))
            httpd = HTTPServer(('0.0.0.0', port), SimpleHandler)
            logger.info(f"Starting simple HTTP server on port {port}")
            httpd.serve_forever()
except ImportError:
    # Fallback to simple HTTP server if FastAPI is not available
    logger.warning("FastAPI not installed. Using simple HTTP server instead.")
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"allkinds"}')
        
        def do_POST(self):
            if self.path == '/webhook':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
                logger.info("Webhook request received but can't be processed in simple mode")
    
    if __name__ == "__main__":
        port = int(os.environ.get("PORT", 8080))
        httpd = HTTPServer(('0.0.0.0', port), SimpleHandler)
        logger.info(f"Starting simple HTTP server on port {port}")
        httpd.serve_forever()
