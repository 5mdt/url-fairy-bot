# bot_test.py

import pytest

from app.bot import handle_message


@pytest.mark.asyncio
async def test_handle_message():
    class MockChat:
        type = "group"  # Set this to "private" to test private chat behavior

    class MockMessage:
        text = "https://example.com"
        chat = MockChat()
        reply_to_message = (
            None  # Set to a message object if you want to test reply behavior
        )

        async def reply(self, text, parse_mode=None):
            # Adjust the assertion as needed based on the expected output for this URL
            assert "Unsupported URL https://example.com/" in text or "success" in text

    message = MockMessage()
    await handle_message(message)
