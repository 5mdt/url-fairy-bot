# messages_test.py

import jinja2
import pytest

from app import messages
from app.config import settings

# --- static one-liners (UFB-0037) ---


def test_start_renders_greeting():
    assert messages.start() == "Hello! Send me a URL to process!"


def test_no_url_prompt_renders_prompt():
    assert messages.no_url_prompt() == "Please send a valid URL to process!"


def test_invalid_url_renders_rejection():
    assert (
        messages.invalid_url()
        == "Invalid URL provided — that doesn't look like a valid URL."
    )


def test_shrug_renders_the_easter_egg():
    assert messages.shrug() == "¯\\_(ツ)_/¯"


# --- link-bearing messages: HTML output ---


def test_download_result_renders_both_links():
    html = messages.download_result("https://example.test/watch/x.html", "https://x.com/a")
    assert '<a href="https://example.test/watch/x.html">⏬ Download</a>' in html
    assert '<a href="https://x.com/a">📎 Source</a>' in html


def test_too_large_prefixes_the_body():
    body = messages.download_result("https://example.test/watch/x.html", "https://x.com/a")
    text = messages.too_large(body)
    assert text.startswith("I cannot upload attachment this big")
    assert body in text


def test_domain_not_allowed_renders_original_link():
    html = messages.domain_not_allowed("https://x.com/a")
    assert "not allowed for downloading" in html
    assert '<a href="https://x.com/a">📎 Original</a>' in html


def test_domain_not_allowed_with_mirror_renders_both_links():
    html = messages.domain_not_allowed_with_mirror(
        "https://mirror.test/a", "https://x.com/a"
    )
    assert "can be parsed better" in html
    assert '<a href="https://mirror.test/a">📎 link</a>' in html
    assert '<a href="https://x.com/a">📎 Source</a>' in html


def test_download_failed_mirror_renders_both_links():
    html = messages.download_failed_mirror("https://mirror.test/a", "https://x.com/a")
    assert "can be parsed better" in html
    assert '<a href="https://mirror.test/a">📎 link</a>' in html
    assert '<a href="https://x.com/a">📎 Source</a>' in html


# --- BUG-0016: HTML-significant characters in URLs are escaped ---


@pytest.mark.parametrize(
    "raw,escaped",
    [
        ("https://x.com/a_b/video/1)x", "https://x.com/a_b/video/1)x"),
        ("https://x.com/a&b", "https://x.com/a&amp;b"),
        ('https://x.com/a"b', "https://x.com/a&#34;b"),
        ("https://x.com/a<b>", "https://x.com/a&lt;b&gt;"),
    ],
)
def test_download_result_escapes_html_significant_characters(raw, escaped):
    html = messages.download_result(raw, "https://x.com/source")
    assert f'href="{escaped}"' in html
    # The link tag itself must stay well-formed regardless of what the URL
    # contains — this is the concrete BUG-0016 regression: a raw f-string
    # interpolation could break the surrounding markup/Markdown link syntax.
    assert '<a href="' in html
    assert "</a>" in html


# --- locale fallback ---


def test_unknown_locale_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(settings, "MESSAGE_LOCALE", "xx")
    assert messages.start() == "Hello! Send me a URL to process!"


# --- StrictUndefined ---


def test_missing_context_variable_raises():
    with pytest.raises(jinja2.exceptions.UndefinedError):
        messages._render("download_result.html.j2")
