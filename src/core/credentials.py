"""
Secure credential handling utility.
This module provides safe methods for accessing credentials and sensitive configuration.
"""

import os
import sys
import re
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

def get_required_env(key: str) -> str:
    """
    Get a required environment variable or exit if not found.
    
    Args:
        key: The environment variable name
        
    Returns:
        The environment variable value
        
    Raises:
        SystemExit: If the environment variable is not set
    """
    value = os.environ.get(key)
    if not value:
        logger.error(f"Required environment variable {key} is not set")
        sys.exit(1)
    return value

def get_optional_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get an optional environment variable with a default fallback.
    
    Args:
        key: The environment variable name
        default: The default value if not found
        
    Returns:
        The environment variable value or default
    """
    return os.environ.get(key, default)

def get_database_url() -> str:
    """
    Get the database URL from environment variables.
    
    Returns:
        The database connection URL
        
    Raises:
        SystemExit: If DATABASE_URL is not set
    """
    return get_required_env("DATABASE_URL")

def get_webhook_config() -> Dict[str, Any]:
    """
    Get webhook configuration from environment variables.
    
    Returns:
        Dictionary with webhook configuration
    """
    use_webhook = get_optional_env("USE_WEBHOOK", "false").lower() in ("true", "1", "yes")
    
    if not use_webhook:
        return {"use_webhook": False}
    
    return {
        "use_webhook": True,
        "webhook_host": get_optional_env("WEBHOOK_HOST", ""),
        "webhook_path": get_optional_env("WEBHOOK_PATH", "/webhook"),
        "webhook_ssl_cert": get_optional_env("WEBHOOK_SSL_CERT", "webhook_cert.pem"),
        "webhook_ssl_priv": get_optional_env("WEBHOOK_SSL_PRIV", "webhook_pkey.pem"),
        "webapp_host": get_optional_env("WEBAPP_HOST", "0.0.0.0"),
        "webapp_port": int(get_optional_env("WEBAPP_PORT", "8080"))
    }

def get_admin_ids() -> List[int]:
    """
    Get admin user IDs from environment.
    
    Returns:
        List of admin user IDs as integers
    """
    admin_ids_str = get_optional_env("ADMIN_IDS", "")
    if not admin_ids_str:
        return []
    
    try:
        # Handle comma-separated list
        if "," in admin_ids_str:
            return [int(id_str.strip()) for id_str in admin_ids_str.split(",") if id_str.strip()]
        
        # Handle JSON-formatted list
        if admin_ids_str.startswith("[") and admin_ids_str.endswith("]"):
            import json
            return json.loads(admin_ids_str)
        
        # Handle single value
        return [int(admin_ids_str)]
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing ADMIN_IDS: {e}")
        return []

def get_api_credentials(service: str) -> Dict[str, str]:
    """
    Get API credentials for a specific service.
    
    Args:
        service: Service name (e.g., "openai", "telegram", "pinecone", "chat")
        
    Returns:
        Dictionary with API credentials
        
    Raises:
        SystemExit: If required credentials are missing
    """
    credentials = {}
    
    if service.lower() == "openai":
        credentials["api_key"] = get_required_env("OPENAI_API_KEY")
        credentials["organization"] = get_optional_env("OPENAI_ORGANIZATION")
    
    elif service.lower() == "telegram":
        credentials["bot_token"] = get_required_env("BOT_TOKEN")
    
    elif service.lower() == "chat":
        # Try to get the token, but don't exit if not found
        token = get_optional_env("chat_BOT_TOKEN")
        if token:
            credentials["bot_token"] = token
        
        # Get the username with a fallback
        username = get_optional_env("chat_BOT_USERNAME", "AllkindsChat")
        credentials["username"] = username
    
    elif service.lower() == "pinecone":
        credentials["api_key"] = get_required_env("PINECONE_API_KEY")
        credentials["environment"] = get_required_env("PINECONE_ENVIRONMENT")
    
    return credentials

def validate_token(token: str, token_type: str = "bot") -> bool:
    """
    Validate token format.
    
    Args:
        token: The token to validate
        token_type: Type of token ("bot", "api_key")
        
    Returns:
        True if valid format, False otherwise
    """
    if not token:
        return False
        
    if token_type == "bot":
        # Telegram bot token format: 123456789:ABCDefGhIJKlmnOPQRstUVwxYZ
        return bool(re.match(r'^\d{8,10}:[A-Za-z0-9_-]{35}$', token))
    
    elif token_type == "api_key" and ":" in token:
        # Simple check for API keys with a colon separator
        parts = token.split(":")
        return len(parts) >= 2 and all(len(p) >= 8 for p in parts)
    
    # Generic check: at least 20 chars, mix of letters and numbers
    return (
        len(token) >= 20 and
        re.search(r'[A-Za-z]', token) is not None and
        re.search(r'[0-9]', token) is not None
    )

def mask_sensitive_data(data: str) -> str:
    """
    Mask sensitive data for safe logging.
    
    Args:
        data: String potentially containing sensitive data
        
    Returns:
        String with sensitive data masked
    """
    # Add masking patterns for sensitive data
    sensitive_patterns = [
        # API keys, tokens, passwords
        (r'"api[_-]?key"\s*:\s*"([^"]{4})([^"]+)([^"]{4})"', r'"api_key":"\1***\3"'),
        (r'"token"\s*:\s*"([^"]{4})([^"]+)([^"]{4})"', r'"token":"\1***\3"'),
        (r'"password"\s*:\s*"([^"]{2})([^"]+)([^"]{2})"', r'"password":"\1***\3"'),
        (r'"secret"\s*:\s*"([^"]{2})([^"]+)([^"]{2})"', r'"secret":"\1***\3"'),
        
        # Database URLs
        (r'(postgresql|mysql|mongodb)://([^:]+):([^@]+)@', r'\1://\2:***@'),
        
        # Telegram bot tokens (format: 123456789:ABCDefGhIJKlmnOPQRstUVwxYZ)
        (r'(\d{4,6})(\d{2,6}):([A-Za-z0-9_-]{4})([A-Za-z0-9_-]{20,})([A-Za-z0-9_-]{4})', r'\1***:\3***\5'),
        
        # Generic long alphanumeric strings that might be tokens
        (r'([A-Za-z0-9_\-\.]{30,})', r'***'),
    ]
    
    result = data
    for pattern, replacement in sensitive_patterns:
        result = re.sub(pattern, replacement, result)
    
    return result

def safe_log_env_vars(include_patterns: List[str] = None, exclude_patterns: List[str] = None) -> None:
    """
    Safely log environment variables with sensitive data masked.
    
    Args:
        include_patterns: Patterns to include (default: all)
        exclude_patterns: Patterns to exclude (default: none)
    """
    if include_patterns is None:
        include_patterns = [".*"]
    
    if exclude_patterns is None:
        exclude_patterns = []
    
    # Filter and mask environment variables
    filtered_env = {}
    for key, value in os.environ.items():
        # Skip if not matching include patterns
        if not any(re.match(pattern, key, re.IGNORECASE) for pattern in include_patterns):
            continue
            
        # Skip if matching exclude patterns
        if any(re.match(pattern, key, re.IGNORECASE) for pattern in exclude_patterns):
            continue
        
        # Mask sensitive values
        if any(sensitive in key.upper() for sensitive in ["TOKEN", "KEY", "SECRET", "PASSWORD", "PASS", "AUTH"]):
            if value and len(value) > 8:
                filtered_env[key] = f"{value[:3]}...{value[-3:]}"
            else:
                filtered_env[key] = "***"
        else:
            filtered_env[key] = value
    
    # Log the filtered environment
    logger.info("=== Environment Variables ===")
    for key, value in sorted(filtered_env.items()):
        logger.info(f"{key}: {value}")
