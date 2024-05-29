# healthcheck.py
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Initialize a router for the health check
router = APIRouter()


@router.get("/healthcheck")
async def healthcheck():
    logger.debug("Health check endpoint was called")
    return perform_healthcheck()


def perform_healthcheck():
    logger.debug("Performing health check")
    # Your health check logic here
    # For demonstration, returning a dummy result
    return {"status": "ok"}
