# api.py
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import cleanup, pages
from .bot import is_polling_alive
from .url_processing import process_url_request


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
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# #UFB-0034
@api_router.get("/healthz")
async def healthz():
    return {"status": "ok"}


# #UFB-0034
@api_router.get("/health")
async def health():
    polling = is_polling_alive()
    seeded = pages.pages_seeded
    cleanup_alive = cleanup.is_cleanup_alive()
    ok = polling and seeded and cleanup_alive
    body: dict[str, str | bool] = {
        "status": "ok" if ok else "degraded",
        "polling": polling,
        "pages_seeded": seeded,
        "cleanup": cleanup_alive,
    }
    return JSONResponse(content=body, status_code=200 if ok else 503)
