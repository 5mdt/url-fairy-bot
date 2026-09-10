# api.py
# -*- coding: utf-8 -*-

import asyncio

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import cleanup, pages
from .bot import is_polling_alive, is_telegram_api_reachable
from .url_processing import DownloadResult, process_url_request


# Define a request model to parse JSON body
# #UFB-0019
class URLRequest(BaseModel):
    url: str


api_router = APIRouter()


# #UFB-0019
@api_router.post("/process_url/")
async def process_url(request: URLRequest = Body(...)):
    try:
        result = await process_url_request(request.url)
        data = result.text if isinstance(result, DownloadResult) else result
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# #UFB-0034
@api_router.get("/healthz")
async def healthz():
    return {"status": "ok"}


# #UFB-0034, #UFB-0036
@api_router.get("/health")
async def health():
    polling = is_polling_alive()
    seeded = pages.pages_seeded
    cleanup_alive = cleanup.is_cleanup_alive()
    # Off the event loop: it's a blocking socket connect, and a hung local
    # server would otherwise stall every other request (and Telegram
    # polling) for up to its timeout. None (TELEGRAM_API_URL unset) must
    # not degrade health — only an explicit False (configured but
    # unreachable) does.
    telegram_api = await asyncio.to_thread(is_telegram_api_reachable)
    ok = bool(polling and seeded and cleanup_alive and telegram_api is not False)
    body: dict[str, str | bool | None] = {
        "status": "ok" if ok else "degraded",
        "polling": polling,
        "pages_seeded": seeded,
        "cleanup": cleanup_alive,
        "telegram_api": telegram_api,
    }
    return JSONResponse(content=body, status_code=200 if ok else 503)
