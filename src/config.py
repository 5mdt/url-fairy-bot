# config.py
# -*- coding: utf-8 -*-

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_URL = os.getenv("BASE_URL", "localhost")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CACHE_DIR = os.getenv("CACHE_DIR", "/cache/")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379").upper()
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# Initialize logging with the configured log level
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

logger.info("Loaded environment variables from .env file")

REQUIRED_VARIABLES = [
    "BASE_URL",
    "BOT_TOKEN",
    "CACHE_DIR",
    "LOG_LEVEL",
    "REDIS_HOST",
    "REDIS_PORT",
]


def check_required_variables(global_vars):
    """
    Check if all required environment variables are set.

    Args:
        global_vars: Dictionary containing global variables.

    Raises:
        ValueError: If any required environment variable is not set or empty.
    """
    for var in REQUIRED_VARIABLES:
        if var not in global_vars or not global_vars[var]:
            logger.error(f"Required environment variable {var} is not set or is empty")
            raise ValueError(
                f"Required environment variable {var} is not set or is empty"
            )
        else:
            logger.debug(f"Environment variable {var} is set to {global_vars[var]}")


# Load configuration variables
check_required_variables(globals())
logger.debug("All required environment variables are set")
