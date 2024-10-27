# test_bot.py

import pytest
from aiogram.types import Message
from app.bot import handle_message

@pytest.mark.asyncio
async def test_handle_message():
    class MockMessage:
        text = "https://example.com"
        async def reply(self, text):
            assert "Unsupported URL https://example.com/" in text or "success" in text

    message = MockMessage()
    await handle_message(message)
