import os
from functools import lru_cache
from typing import List, Optional, Union, Any

from loguru import logger
from pydantic_settings import BaseSettings
from pydantic import field_validator, Field


class Settings(BaseSettings):
    """Application settings."""
    # General settings
    debug: bool = False
    app_name: str = "Allkinds Chat Bot"
    
    # Bot specific settings
    CHAT_BOT_TOKEN: str = "dummy_token"  # Default prevents validation error
    # ADMIN_IDS should hold the final list of ints
    ADMIN_IDS: List[int] = [123456789]  # Default prevents validation error
    CHAT_BOT_USERNAME: str = Field(default=os.environ.get("CHAT_BOT_USERNAME", "AllkindsChatBot"), alias="CHAT_BOT_USERNAME")
    
    # Webhook configuration
    USE_WEBHOOK: bool = Field(default=bool(os.environ.get("RAILWAY_ENVIRONMENT")), alias="USE_WEBHOOK")  # Use webhook on Railway
    WEBHOOK_HOST: str = Field(default="https://allkindsteambot-production.up.railway.app", alias='WEBHOOK_HOST')
    WEBHOOK_PATH: str = Field(default="/bot/webhook", alias='WEBHOOK_PATH')  # Use /bot/webhook path
    WEBHOOK_SSL_CERT: str = Field(default="webhook_cert.pem", alias='WEBHOOK_SSL_CERT')
    WEBHOOK_SSL_PRIV: str = Field(default="webhook_pkey.pem", alias='WEBHOOK_SSL_PRIV')
    WEBAPP_HOST: str = Field(default="0.0.0.0", alias='WEBAPP_HOST')  # Default for Railway
    WEBAPP_PORT: int = Field(default=int(os.environ.get('PORT', 8080)), alias='WEBAPP_PORT')  # Use PORT from environment or default to 8080

    @field_validator('ADMIN_IDS', mode='before')
    @classmethod
    def _parse_admin_ids(cls, v: Any) -> List[int]:
        """Parse ADMIN_IDS from various formats into a list of integers."""
        logger.info(f"Parsing ADMIN_IDS from value type: {type(v)}")
        
        # Already a list, just return it
        if isinstance(v, list):
            logger.info(f"ADMIN_IDS is already a list: {v}")
            return v
        
        # Single integer value
        if isinstance(v, int):
            logger.info(f"Received single admin ID as int: {v}")
            return [v]
        
        # None or empty value, return default
        if not v:
            logger.warning("Empty ADMIN_IDS, using default")
            return [123456789]  # Default admin ID
        
        # Handle string values
        if isinstance(v, str):
            try:
                # Try parsing as comma-separated list
                if ',' in v:
                    logger.info(f"Parsing comma-separated ADMIN_IDS: {v}")
                    return [int(id_str.strip()) for id_str in v.split(',') if id_str.strip().isdigit()]
                
                # Try parsing as a single number
                if v.strip().isdigit():
                    logger.info(f"Parsing single ADMIN_ID string: {v}")
                    return [int(v.strip())]
                
                # Try parsing as JSON array if it looks like one
                if v.strip().startswith('[') and v.strip().endswith(']'):
                    logger.info(f"Parsing JSON array ADMIN_IDS: {v}")
                    import json
                    try:
                        ids = json.loads(v)
                        if isinstance(ids, list):
                            return [int(id_val) for id_val in ids if isinstance(id_val, (int, str)) and (isinstance(id_val, int) or id_val.isdigit())]
                    except Exception as e:
                        logger.error(f"Failed to parse ADMIN_IDS as JSON: {e}")
            except Exception as e:
                logger.error(f"Failed to parse ADMIN_IDS string '{v}': {e}")
        
        # If we get here, something went wrong, return default
        logger.warning(f"Could not properly parse ADMIN_IDS, using default. Value was: {v} (type: {type(v)})")
        return [123456789]  # Default admin ID

    # Database settings
    db_url: str = Field(default="sqlite+aiosqlite:///./allkinds.db", alias='DATABASE_URL') # Use alias for Railway compatibility
    
    # Redis settings
    REDIS_URL: str = Field(default="", alias='REDIS_URL')
    
    # OpenAI settings
    openai_api_key: str = Field(default="", alias='OPENAI_API_KEY')
    
    # Pinecone settings
    pinecone_api_key: str = Field(default="", alias='PINECONE_API_KEY')
    pinecone_environment: str = Field(default="", alias='PINECONE_ENVIRONMENT')
    pinecone_index_name: str = Field(default="allkinds", alias='PINECONE_INDEX_NAME')
    
    class Config:
        env_file = ".env"
        extra = "ignore" # Ignore any extra fields not defined above


@lru_cache
def get_settings() -> Settings:
    """Get application settings singleton."""
    # Clear cache if needed for testing: get_settings.cache_clear()
    return Settings() 