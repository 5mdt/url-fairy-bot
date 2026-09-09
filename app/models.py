# models.py
from pydantic import BaseModel, HttpUrl


# #UFB-0006
class URLMessage(BaseModel):
    url: HttpUrl
    is_group_chat: bool = False
