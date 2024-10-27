# api.py
# -*- coding: utf-8 -*-

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from .url_processing import process_url_request


# Define a request model to parse JSON body
class URLRequest(BaseModel):
    url: str


api_router = APIRouter()


@api_router.post("/process_url/")
async def process_url(request: URLRequest = Body(...)):
    try:
        result = await process_url_request(request.url)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
