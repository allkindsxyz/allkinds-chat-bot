#!/usr/bin/env python3
"""
Script to kill all running bot instances and start a new one
"""
import os
import sys
import time
import signal
import subprocess
import psutil

def kill_bot_processes():
    """Find and kill all running bot processes"""
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            # Check if this is a bot process
            if ('python' in cmdline and 'src.main' in cmdline) or \
               ('src.chat_bot.main' in cmdline):
                print(f"Killing process {proc.info['pid']}: {cmdline}")
                # Try graceful termination first
                proc.terminate()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except Exception as e:
            print(f"Error checking process: {e}")
    
    # If we killed any processes, wait a moment for them to terminate
    if killed_count > 0:
        print(f"Waiting for {killed_count} processes to terminate...")
        time.sleep(2)
        
        # Force kill any that didn't terminate gracefully
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if ('python' in cmdline and 'src.main' in cmdline) or \
                   ('src.chat_bot.main' in cmdline):
                    print(f"Force killing process {proc.info['pid']}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except Exception as e:
                print(f"Error force killing process: {e}")
    
    return killed_count

def start_new_instance():
    """Start a new instance of the bot"""
    print("Starting new bot instance...")
    
    # Use subprocess to start the bot in a new process
    try:
        # Use Poetry to run the bot
        process = subprocess.Popen(
            ["poetry", "run", "python", "-m", "src.main"],
            stdout=open("logs/bot_output.log", "a"),
            stderr=subprocess.STDOUT,
            # Detach the process so it continues running after this script ends
            start_new_session=True
        )
        
        print(f"Bot started with PID: {process.pid}")
        
        # Wait a moment to see if it crashes immediately
        time.sleep(2)
        if process.poll() is not None:
            print(f"Warning: Bot process exited immediately with code {process.returncode}")
            print("Check logs/bot_output.log for details")
            return False
        
        return True
    except Exception as e:
        print(f"Error starting bot: {e}")
        return False

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    try:
        subprocess.run(["poetry", "add", "requests", "psutil"], check=True)
        return True
    except Exception as e:
        print(f"Error installing packages: {e}")
        return False

if __name__ == "__main__":
    print("Bot Manager Script")
    print("==================")
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Check for and install dependencies
    install_requirements()
    
    # Kill any running instances
    killed = kill_bot_processes()
    print(f"Killed {killed} running bot instances")
    
    # Start a new instance
    if start_new_instance():
        print("Bot successfully started in background")
        print("Check logs/bot_output.log for output")
        sys.exit(0)
    else:
        print("Failed to start bot")
        sys.exit(1) 