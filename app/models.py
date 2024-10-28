# models.py
from pydantic import BaseModel, HttpUrl


class URLMessage(BaseModel):
    url: HttpUrl
    is_group_chat: bool = False
