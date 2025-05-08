#!/usr/bin/env python3
"""
Simple health check script for Railway
This script is used by Railway to check if the service is healthy
"""
import os
import sys
import requests
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("healthcheck")

def main():
    """Main health check function."""
    logger.info("Running health check")
    
    # Get port from environment
    port = os.environ.get("PORT", "8000")
    
    # URL to check
    url = f"http://localhost:{port}/health"
    
    try:
        # Make the request
        start_time = time.time()
        response = requests.get(url, timeout=5)
        duration = time.time() - start_time
        
        # Check if successful
        if response.status_code == 200:
            logger.info(f"Health check successful: {response.status_code} in {duration:.2f}s")
            logger.info(f"Response: {response.text}")
            # Return success
            return 0
        else:
            logger.error(f"Health check failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            # Return failure
            return 1
    except requests.RequestException as e:
        logger.error(f"Health check request failed: {e}")
        # Return failure
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during health check: {e}")
        # Return failure
        return 1

if __name__ == "__main__":
    # Run the health check and exit with the appropriate code
    sys.exit(main()) 