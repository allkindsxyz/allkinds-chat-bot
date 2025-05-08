import http.server
import socketserver
import os
import subprocess
import time
import threading
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("health_server")

# Use PORT from environment variable (Railway sets this)
PORT = int(os.environ.get("PORT", 8080))

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to use our logger instead of stderr
        logger.info("%s - %s", self.address_string(), format % args)
    
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            logger.info("Health check requested")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","message":"Bot is running"}')
        elif self.path == "/status":
            # Get bot process status
            try:
                output = subprocess.check_output("ps aux | grep python3", shell=True).decode('utf-8')
                bot_status = "Bot processes:\n" + output
            except Exception as e:
                bot_status = f"Error getting bot status: {str(e)}"
                
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(bot_status.encode('utf-8'))
        elif self.path == "/logs":
            # Get last 50 lines of bot logs
            try:
                if os.path.exists("bot.log"):
                    with open("bot.log", "r") as f:
                        logs = f.readlines()
                        logs = logs[-50:] if len(logs) > 50 else logs
                        log_content = "Last 50 lines of bot.log:\n" + "".join(logs)
                else:
                    log_content = "Bot log file does not exist yet"
            except Exception as e:
                log_content = f"Error getting bot logs: {str(e)}"
                
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(log_content.encode('utf-8'))
        elif self.path == "/restart":
            # Restart the bot process
            try:
                subprocess.run("pkill -f 'python3 -m src.bot.main'", shell=True)
                time.sleep(2)
                subprocess.Popen("nohup python3 -m src.bot.main > bot.log 2>&1 &", shell=True)
                restart_response = "Bot restarted successfully"
            except Exception as e:
                restart_response = f"Error restarting bot: {str(e)}"
                
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(restart_response.encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found. Available endpoints: /health, /status, /logs, /restart")

def run_server():
    """Run the server in a way that can be properly terminated"""
    try:
        # Ensure the TCP server can reuse the address
        socketserver.TCPServer.allow_reuse_address = True
        
        # Create the server with the handler
        with socketserver.TCPServer(("", PORT), HealthHandler) as httpd:
            logger.info(f"Health check server running at http://0.0.0.0:{PORT}")
            logger.info(f"Available endpoints: /health, /status, /logs, /restart")
            
            # Serve until interrupted
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Health server stopped by keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error running health server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info(f"Starting health check server on port {PORT}")
    logger.info(f"Available endpoints:")
    logger.info(f"  - /health: Basic health check")
    logger.info(f"  - /status: Show bot processes")
    logger.info(f"  - /logs: Show last 50 lines of bot logs")
    logger.info(f"  - /restart: Restart the bot process")
    
    # Check if 'daemon' argument is provided
    if len(sys.argv) > 1 and sys.argv[1] == 'daemon':
        # Run in daemon mode
        logger.info("Starting health server in daemon mode")
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        # Keep the main thread alive to prevent the daemon thread from exiting
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Health server daemon stopped by keyboard interrupt")
            sys.exit(0)
    else:
        # Run in foreground mode
        run_server() 