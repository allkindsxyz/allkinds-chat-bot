import logging
import functools
import time
import os
import traceback
import inspect
import asyncio
from datetime import datetime
from typing import Any, Callable, Optional

# Configure a separate logger for diagnostics
logger = logging.getLogger("railway_diagnostics")

# Track performance metrics
metrics = {
    "webhook_calls": 0,
    "db_operations": 0,
    "command_calls": 0,
    "errors": 0,
    "last_webhook_time": None
}

# Check if we're in Railway
IS_RAILWAY = os.environ.get("RAILWAY_ENVIRONMENT") is not None

def log_environment_vars():
    """Log all environment variables for debugging purposes."""
    # Get the main logger
    main_logger = logging.getLogger(__name__)
    
    # Create a filtered copy of environment variables (hide secrets)
    safe_env = {}
    
    # List of keys that should be partially hidden
    sensitive_keys = ['TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'PASS', 'AUTH']
    
    for k, v in os.environ.items():
        # Check if this is a sensitive variable
        is_sensitive = any(secret_key in k.upper() for secret_key in sensitive_keys)
        
        if is_sensitive and v:
            # Show only the first and last 3 characters of sensitive values
            if len(v) > 8:
                safe_env[k] = f"{v[:3]}...{v[-3:]}"
            else:
                safe_env[k] = "***"
        else:
            safe_env[k] = v
    
    # Log environment variables
    main_logger.info("===== ENVIRONMENT VARIABLES =====")
    
    # Log important variables first
    priority_vars = ['RAILWAY_ENVIRONMENT', 'RAILWAY_SERVICE_NAME', 'PORT', 
                    'RAILWAY_PUBLIC_DOMAIN', 'RAILWAY_PUBLIC_URL', 'WEBHOOK_DOMAIN',
                    'BOT_TOKEN', 'DATABASE_URL', 'ADMIN_IDS']
    
    for var in priority_vars:
        if var in safe_env:
            main_logger.info(f"{var}: {safe_env[var]}")
    
    # Then log all other variables
    main_logger.info("--- Other Environment Variables ---")
    for k, v in sorted(safe_env.items()):
        if k not in priority_vars:
            main_logger.info(f"{k}: {v}")
    
    main_logger.info("=================================")

def configure_diagnostics():
    """Configure diagnostics logging"""
    if not IS_RAILWAY:
        return
    
    # Create a separate handler for diagnostics
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | DIAG | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    # Set up the logger
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    # Log startup information
    logger.info("==== RAILWAY DIAGNOSTICS INITIALIZED ====")
    logger.info(f"Environment variables: {dict(os.environ)}")
    
    # Log Python and asyncio info
    logger.info(f"Python version: {os.sys.version}")
    logger.info(f"Asyncio event loop: {asyncio.get_event_loop().__class__.__name__}")
    
def track_webhook(func):
    """Decorator to track webhook calls"""
    @functools.wraps(func)
    async def wrapper(request, *args, **kwargs):
        if not IS_RAILWAY:
            return await func(request, *args, **kwargs)
        
        metrics["webhook_calls"] += 1
        metrics["last_webhook_time"] = datetime.now().isoformat()
        
        method = request.method
        headers = dict(request.headers)
        ip = request.client.host if hasattr(request, 'client') and hasattr(request.client, 'host') else "unknown"
        
        logger.info(f"WEBHOOK CALL #{metrics['webhook_calls']} from {ip} using {method}")
        
        try:
            # Log request content
            body = None
            try:
                body = await request.json()
                logger.info(f"WEBHOOK BODY: {body}")
            except Exception as e:
                try:
                    raw_text = await request.text()
                    logger.info(f"WEBHOOK RAW TEXT: {raw_text[:500]}")
                except:
                    logger.info("Could not read webhook body")
            
            # Execute the handler
            start_time = time.time()
            response = await func(request, *args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(f"WEBHOOK HANDLER completed in {execution_time:.2f}s")
            return response
        except Exception as e:
            metrics["errors"] += 1
            logger.error(f"WEBHOOK ERROR: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    return wrapper

def track_command(func):
    """Decorator to track command execution"""
    @functools.wraps(func)
    async def wrapper(message, *args, **kwargs):
        if not IS_RAILWAY:
            return await func(message, *args, **kwargs)
        
        metrics["command_calls"] += 1
        
        user_id = message.from_user.id if hasattr(message, 'from_user') else "unknown"
        chat_id = message.chat.id if hasattr(message, 'chat') else "unknown"
        command = message.text if hasattr(message, 'text') else "unknown"
        
        logger.info(f"COMMAND #{metrics['command_calls']} from user {user_id} in chat {chat_id}: {command}")
        
        try:
            # Execute the handler
            start_time = time.time()
            result = await func(message, *args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(f"COMMAND HANDLER {func.__name__} completed in {execution_time:.2f}s")
            return result
        except Exception as e:
            metrics["errors"] += 1
            logger.error(f"COMMAND ERROR in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    return wrapper

def track_db(func):
    """Decorator to track database operations"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if not IS_RAILWAY:
            return await func(*args, **kwargs)
        
        metrics["db_operations"] += 1
        
        # Try to get session from args
        session = None
        for arg in args:
            if hasattr(arg, 'execute') and hasattr(arg, 'commit'):
                session = arg
                break
        
        if not session and 'session' in kwargs:
            session = kwargs['session']
        
        # Get function signature
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        # Create a descriptor of the operation
        arg_desc = {
            k: (str(v) if not isinstance(v, int) else v) 
            for k, v in bound_args.arguments.items() 
            if k != 'session' and k != 'self'
        }
        
        logger.info(f"DB OPERATION #{metrics['db_operations']} - {func.__name__} with args: {arg_desc}")
        
        try:
            # Execute the operation
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Log the result type 
            result_type = type(result).__name__
            if hasattr(result, '__len__'):
                logger.info(f"DB OPERATION {func.__name__} completed in {execution_time:.2f}s - returned {result_type} with {len(result)} items")
            else:
                logger.info(f"DB OPERATION {func.__name__} completed in {execution_time:.2f}s - returned {result_type}")
            
            return result
        except Exception as e:
            metrics["errors"] += 1
            logger.error(f"DB ERROR in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    return wrapper

def get_diagnostics_report() -> str:
    """Get a diagnostics report"""
    if not IS_RAILWAY:
        return "Diagnostics only available in Railway environment"
    
    report = [
        "==== RAILWAY DIAGNOSTICS REPORT ====",
        f"Webhook calls: {metrics['webhook_calls']}",
        f"DB operations: {metrics['db_operations']}",
        f"Command calls: {metrics['command_calls']}",
        f"Errors: {metrics['errors']}",
        f"Last webhook time: {metrics['last_webhook_time']}",
        f"Current time: {datetime.now().isoformat()}",
    ]
    
    return "\n".join(report) 