# healthcheck.py
# -*- coding: utf-8 -*-

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Initialize a router for the health check
router = APIRouter()


@router.get("/healthcheck")
async def healthcheck():
    """
    Perform a health check via REST API

    Returns:
        dict: Status of the health check.
    """
    logger.debug("Health check endpoint was called")
    return perform_healthcheck()


def perform_healthcheck():
    """
    Perform the health check logic.

    Returns:
        dict: Status of the health check.
    """
    logger.debug("Performing health check")
    # Your health check logic here
    # For demonstration, returning a dummy result
    return {"status": "ok"}
