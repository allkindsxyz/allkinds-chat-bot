#!/usr/bin/env python3
"""
Bot manager for controlling Allkinds Chat Bot lifecycle 
- starting, stopping, and health checks
"""

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
import atexit
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("bot_manager")

# Modules
CHAT_BOT_MODULE = "src.chat_bot.main"

# PID files
CHAT_PID_FILE = "chat_bot.pid"

# Logs directory
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

def is_process_running(pid):
    """Check if a process with the given PID is running."""
    try:
        # Send signal 0 to the process - doesn't actually send a signal
        # but checks if the process exists
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    
def read_pid_file(pid_file):
    """Read a PID from a file."""
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
            return pid
    except (IOError, ValueError):
        return None

def write_pid_file(pid_file, pid):
    """Write a PID to a file."""
    with open(pid_file, 'w') as f:
        f.write(str(pid))

def remove_pid_file(pid_file):
    """Remove a PID file."""
    try:
        os.remove(pid_file)
    except OSError:
        pass

def kill_bot_process(pid_file):
    """Kill a bot process identified by its PID file."""
    pid = read_pid_file(pid_file)
    if pid and is_process_running(pid):
        try:
            logger.info(f"Killing bot process with PID {pid}")
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to terminate
            for _ in range(10):  # wait up to 5 seconds
                if not is_process_running(pid):
                    break
                time.sleep(0.5)
        
        # Force kill if still running
            if is_process_running(pid):
                logger.warning(f"Process {pid} didn't terminate gracefully. Force killing...")
            os.kill(pid, signal.SIGKILL)
        
            remove_pid_file(pid_file)
        return True
        except OSError as e:
            logger.error(f"Error killing process {pid}: {e}")
    elif pid:
        logger.info(f"Process {pid} is not running. Removing PID file.")
        remove_pid_file(pid_file)
    else:
        logger.info(f"No PID found in {pid_file}.")
        return False

def kill_all_bot_processes():
    """Find and kill all running bot processes."""
    killed = False
    import psutil
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            # Check if this is a bot process
            if (CHAT_BOT_MODULE in cmdline):
                logger.info(f"Killing process {proc.info['pid']}: {cmdline}")
                try:
                proc.terminate()
                    killed = True
                except psutil.NoSuchProcess:
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Clean up PID files
    remove_pid_file(CHAT_PID_FILE)
    
    return killed

def check_bot_health(pid_file):
    """Check if a bot is healthy by verifying if it's running."""
    pid = read_pid_file(pid_file)
    if pid and is_process_running(pid):
                return True
        return False

def start_bot(module_name, pid_file, log_file):
    """Start a bot as a subprocess and save its PID."""
    
    # Check if already running
    pid = read_pid_file(pid_file)
    if pid and is_process_running(pid):
        logger.info(f"Bot is already running with PID {pid}")
        return pid
    
    # Start the bot
    logger.info(f"Starting {module_name}...")
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Open log file
    log_fd = open(log_file, 'a')
    
    # Start the bot process
    process = subprocess.Popen(
        [sys.executable, "-m", module_name],
        stdout=log_fd,
        stderr=log_fd,
        start_new_session=True  # Detach the process from the current session
    )
    
    # Save the PID
    pid = process.pid
    write_pid_file(pid_file, pid)
    
    logger.info(f"Started {module_name} with PID {pid}")
    return pid

def stop_bot(pid_file, bot_type="chat"):
    """Stop a bot process."""
    logger.info(f"Stopping {bot_type} bot...")
    return kill_bot_process(pid_file)

def restart_bot(module_name, pid_file, log_file, bot_type="chat"):
    """Restart a bot by stopping and starting it."""
    logger.info(f"Restarting {bot_type} bot...")
    stop_bot(pid_file, bot_type)
    return start_bot(module_name, pid_file, log_file)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Manage Allkinds bot processes')
    
    # Create a mutually exclusive group for action commands
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--start', action='store_true', help='Start the bot')
    group.add_argument('--stop', action='store_true', help='Stop the bot')
    group.add_argument('--restart', action='store_true', help='Restart the bot')
    group.add_argument('--status', action='store_true', help='Check bot status')
    group.add_argument('--kill-all', action='store_true', help='Kill all running bot processes')
    
    # Add optional arguments
    parser.add_argument('--type', choices=['chat'], 
                        default='chat', help='Bot type to manage')
    
    return parser.parse_args()

def run_manager():
    """Main function to run the bot manager."""
    # Create logs directory if it doesn't exist
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    args = parse_arguments()
    
    # Set up PID and log files based on bot type
    if args.type == 'chat':
        module_name = CHAT_BOT_MODULE
        pid_file = CHAT_PID_FILE
        log_file = f"{LOGS_DIR}/chat_bot.log"
    
    # Register cleanup function
    def cleanup():
        """Clean up function to be called when the manager exits."""
        pass
    
    atexit.register(cleanup)
    
    # Execute the requested action
    if args.start:
        logger.info(f"Starting {args.type} bot...")
        start_bot(module_name, pid_file, log_file)
    
    elif args.stop:
        logger.info(f"Stopping {args.type} bot...")
        if stop_bot(pid_file, args.type):
            logger.info(f"{args.type.capitalize()} bot stopped successfully")
        else:
            logger.info(f"{args.type.capitalize()} bot was not running")
    
    elif args.restart:
        logger.info(f"Restarting {args.type} bot...")
        restart_bot(module_name, pid_file, log_file, args.type)
    
    elif args.status:
        if check_bot_health(pid_file):
            pid = read_pid_file(pid_file)
            logger.info(f"{args.type.capitalize()} bot is running with PID {pid}")
            sys.exit(0)
        else:
            logger.info(f"{args.type.capitalize()} bot is not running")
            sys.exit(1)
    
    elif args.kill_all:
        logger.info("Killing all bot processes...")
        if kill_all_bot_processes():
            logger.info("All bot processes killed successfully")
        else:
            logger.info("No bot processes found to kill")

if __name__ == "__main__":
    run_manager() 