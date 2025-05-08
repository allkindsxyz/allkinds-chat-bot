#!/usr/bin/env python3
"""
Bot Manager - A centralized script to manage Allkinds bots
Replaces multiple shell scripts with a single Python interface
"""
import os
import sys
import time
import signal
import asyncio
import argparse
import subprocess
import json
import ssl
import aiohttp
from pathlib import Path
from dotenv import load_dotenv
import psutil

# Constants
MAIN_BOT_MODULE = "src.bot.main"
chat_BOT_MODULE = "src.chat_bot.main"
MAIN_PID_FILE = "main_bot.pid"
COMM_PID_FILE = "chat_bot.pid"
LOGS_DIR = "logs"

# Create logs directory if needed
Path(LOGS_DIR).mkdir(exist_ok=True)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
chat_BOT_TOKEN = os.getenv("chat_BOT_TOKEN")

# SSL context that ignores verification for debugging
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def get_process_status(pid_file):
    """Check if a process is running based on its PID file"""
    if not Path(pid_file).exists():
        return False, None, "No PID file"
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        process = psutil.Process(pid)
        if process.is_running():
            status = process.status()
            return True, pid, status
        else:
            return False, pid, "Process not running"
    except (ProcessLookupError, psutil.NoSuchProcess):
        return False, pid, "Stale PID file"
    except Exception as e:
        return False, None, f"Error: {str(e)}"

def kill_process(pid_file):
    """Kill a process by its PID file"""
    if not Path(pid_file).exists():
        print(f"PID file {pid_file} not found")
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Try graceful termination first
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to terminate
        for _ in range(10):
            try:
                os.kill(pid, 0)  # Check if process exists
                time.sleep(0.5)
            except OSError:
                break  # Process terminated
        
        # Force kill if still running
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
            print(f"Process {pid} force-killed")
        except OSError:
            print(f"Process {pid} gracefully terminated")
        
        # Remove PID file
        os.remove(pid_file)
        return True
    except Exception as e:
        print(f"Error killing process: {e}")
        return False

def kill_all_bots():
    """Kill all bot processes"""
    # Try to kill by PID file first
    main_killed = kill_process(MAIN_PID_FILE)
    comm_killed = kill_process(COMM_PID_FILE)
    
    # Also search for any remaining bot processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if (MAIN_BOT_MODULE in cmdline or 
                chat_BOT_MODULE in cmdline):
                proc.terminate()
                print(f"Terminated bot process: {proc.info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except Exception as e:
            print(f"Error terminating process: {e}")
    
    time.sleep(2)  # Give processes time to die
    return main_killed, comm_killed

def start_bot(module, pid_file, log_file):
    """Start a bot as a background process"""
    try:
        # Create logs directory if it doesn't exist
        Path(LOGS_DIR).mkdir(exist_ok=True)
        
        # Create log file if it doesn't exist
        Path(log_file).touch(exist_ok=True)
        
        # Remove PID file if it exists but process isn't running
        if Path(pid_file).exists():
            try:
                with open(pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                try:
                    # Check if process exists
                    os.kill(old_pid, 0)
                    print(f"Process {old_pid} is still running. Stopping it first.")
                    os.kill(old_pid, signal.SIGTERM)
                    time.sleep(2)
                except OSError:
                    # Process doesn't exist, can remove PID file
                    pass
                os.remove(pid_file)
            except Exception as e:
                print(f"Error checking old PID: {e}")
                # Still try to remove it
                try:
                    os.remove(pid_file)
                except:
                    pass
        
        print(f"Starting {module}...")
        # Use different process creation method based on platform
        if os.name == 'posix':  # Unix-like
            # Start the process using popen with proper detachment
            with open(log_file, 'a') as log:
                process = subprocess.Popen(
                    [sys.executable, '-m', module],
                    stdout=log,
                    stderr=log,
                    preexec_fn=os.setpgrp,  # Detach from parent process
                    close_fds=True
                )
        else:  # Windows
            # Use DETACHED_PROCESS flag on Windows
            with open(log_file, 'a') as log:
                process = subprocess.Popen(
                    [sys.executable, '-m', module],
                    stdout=log,
                    stderr=log,
                    creationflags=subprocess.DETACHED_PROCESS,
                    close_fds=True
                )
        
        # Write PID to file
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        print(f"Started {module} with PID {process.pid}")
        # Wait a moment to ensure process started correctly
        time.sleep(1)
        
        # Verify process is still running
        try:
            proc = psutil.Process(process.pid)
            if proc.is_running():
                print(f"Process {process.pid} is running successfully")
                return True
            else:
                print(f"Process {process.pid} failed to start properly")
                return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"Process {process.pid} failed to start or terminated immediately")
            return False
    except Exception as e:
        print(f"Error starting {module}: {e}")
        return False

async def delete_webhook(token):
    """Delete a bot's webhook"""
    if not token:
        print("No token provided")
        return None
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            url = f"https://api.telegram.org/bot{token}/deleteWebhook"
            async with session.get(url) as response:
                result = await response.json()
                return result
    except Exception as e:
        print(f"Error deleting webhook: {e}")
        return None

async def get_webhook_info(token):
    """Get a bot's webhook info"""
    if not token:
        print("No token provided")
        return None
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
            async with session.get(url) as response:
                result = await response.json()
                return result
    except Exception as e:
        print(f"Error getting webhook info: {e}")
        return None

async def reset_webhooks():
    """Reset webhooks for both bots"""
    # Reset main bot webhook
    print("Resetting main bot webhook...")
    main_result = await delete_webhook(BOT_TOKEN)
    if main_result:
        print(f"Main bot webhook reset: {json.dumps(main_result)}")
    
    # Comment out chat bot reset to make the main bot start independently
    """
    # Reset chat bot webhook
    print("Resetting chat bot webhook...")
    from reset_chat_bot import verify_token, reset_bot
    token_valid = await verify_token()
    if token_valid:
        success = await reset_bot()
        if success:
            print("chat bot reset successfully")
        else:
            print("Failed to reset chat bot")
    else:
        comm_result = await delete_webhook(chat_BOT_TOKEN)
        if comm_result:
            print(f"chat bot webhook reset: {json.dumps(comm_result)}")
    """
    
    # Get webhook info
    main_info = await get_webhook_info(BOT_TOKEN)
    if main_info:
        print(f"Main bot webhook info: {json.dumps(main_info)}")
    
    return True

def check_bots_status():
    """Check the status of both bots"""
    print("===== BOT STATUS CHECK =====\n")
    
    # Check main bot
    main_running, main_pid, main_status = get_process_status(MAIN_PID_FILE)
    if main_running:
        print(f"✅ Main bot is running (PID: {main_pid}, Status: {main_status})")
    else:
        print(f"❌ Main bot is not running ({main_status})")
    
    # Check chat bot
    comm_running, comm_pid, comm_status = get_process_status(COMM_PID_FILE)
    if comm_running:
        print(f"✅ chat bot is running (PID: {comm_pid}, Status: {comm_status})")
    else:
        print(f"❌ chat bot is not running ({comm_status})")
    
    print("\n===== BOT CONTROLS =====")
    print("Run 'python bot_manager.py start' to start bots")
    print("Run 'python bot_manager.py stop' to stop bots")
    print("Run 'python bot_manager.py status' to check status")
    print("Run 'python bot_manager.py reset' to reset webhooks")
    
    print("\n===== LOG OPTIONS =====")
    print("Run 'python bot_manager.py logs main' to view main bot logs")
    print("Run 'python bot_manager.py logs chat' to view chat bot logs")
    
    return main_running, comm_running

def view_logs(bot_type, lines=50):
    """View bot logs"""
    log_file = f"{LOGS_DIR}/main_bot.log" if bot_type == 'main' else f"{LOGS_DIR}/chat_bot.log"
    
    if not Path(log_file).exists():
        print(f"Log file {log_file} not found")
        return False
    
    try:
        # Use tail command on Unix-like systems
        if os.name == 'posix':
            subprocess.run(['tail', '-n', str(lines), log_file])
        else:
            # Manual implementation for Windows
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    print(line, end='')
        return True
    except Exception as e:
        print(f"Error viewing logs: {e}")
        return False

async def start_bots(which_bots='both'):
    """Start the selected bots"""
    # Reset webhooks first
    await reset_webhooks()
    
    # Kill any existing processes
    kill_all_bots()
    
    # Start selected bots
    if which_bots in ['main', 'both']:
        start_bot(
            MAIN_BOT_MODULE,
            MAIN_PID_FILE,
            f"{LOGS_DIR}/main_bot.log"
        )
    
    # Comment out chat bot start to ensure main bot works independently
    """
    if which_bots in ['chat', 'both']:
        start_bot(
            chat_BOT_MODULE,
            COMM_PID_FILE,
            f"{LOGS_DIR}/chat_bot.log"
        )
    """
    
    print("Done! Bots are running in the background.")
    return True

def stop_bots():
    """Stop all running bots"""
    main_killed, comm_killed = kill_all_bots()
    
    if main_killed:
        print("Main bot stopped.")
    else:
        print("Main bot was not running or could not be stopped.")
    
    if comm_killed:
        print("chat bot stopped.")
    else:
        print("chat bot was not running or could not be stopped.")
    
    print("All bots stopped.")
    return True

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Manage Allkinds Telegram bots')
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start bots')
    start_parser.add_argument('bot', nargs='?', choices=['main', 'chat', 'both'], 
                            default='both', help='Which bot to start (default: both)')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop all bots')
    
    # Status command
    subparsers.add_parser('status', help='Check bot status')
    
    # Reset command
    subparsers.add_parser('reset', help='Reset webhooks')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='View bot logs')
    logs_parser.add_argument('bot', choices=['main', 'chat'], 
                           help='Which bot logs to view')
    logs_parser.add_argument('-n', '--lines', type=int, default=50,
                           help='Number of lines to show (default: 50)')
    
    return parser.parse_args()

async def main():
    """Main entry point"""
    args = parse_args()
    
    if args.command == 'start':
        await start_bots(args.bot)
    elif args.command == 'stop':
        stop_bots()
    elif args.command == 'status':
        check_bots_status()
    elif args.command == 'reset':
        await reset_webhooks()
    elif args.command == 'logs':
        view_logs(args.bot, args.lines)
    else:
        # If no command specified, show status and prompt for action
        check_bots_status()
        
        print("\nWhat would you like to do?")
        print("1. Start the main bot")
        print("2. Start the chat bot")
        print("3. Start both bots")
        print("4. Stop all bots")
        print("5. Reset webhooks")
        print("6. View main bot logs")
        print("7. View chat bot logs")
        choice = input("Enter choice (1-7): ")
        
        if choice == '1':
            await start_bots('main')
        elif choice == '2':
            await start_bots('chat')
        elif choice == '3':
            await start_bots('both')
        elif choice == '4':
            stop_bots()
        elif choice == '5':
            await reset_webhooks()
        elif choice == '6':
            view_logs('main')
        elif choice == '7':
            view_logs('chat')
        else:
            print("Invalid choice")

if __name__ == "__main__":
    # Check if psutil module is installed
    try:
        import psutil
    except ImportError:
        print("Error: The psutil module is required for this script.")
        print("Please install it using: pip install psutil")
        sys.exit(1)
        
    asyncio.run(main()) 