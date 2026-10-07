# reports_test.py
# #UFB-0051: report-broken-link button.

import hashlib
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import messages, metadata, reports
from app.bot import dp, report_broken_link
from app.config import settings
from app.download import url_to_filename_stem
from app.url_processing import process_url_request

URL = "https://www.tiktok.com/@u/video/1"


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "REPORT_RATE_LIMIT", 3)
    monkeypatch.setattr(settings, "REPORT_RATE_WINDOW", 3600)
    reports.reset()


def _token(url=URL, reason="failure"):
    reports.keyboard_for(reports.FailureReply("x", url, reason))
    return reports.token_for(url)


# --- callback data ---


# #UFB-0051
def test_token_is_16_hex_of_sha256_and_callback_fits_telegram_limit():
    token = reports.token_for(URL)
    assert token == hashlib.sha256(URL.encode()).hexdigest()[:16]
    long_url = "https://example.org/" + "a" * 3000
    assert len(reports.callback_data(reports.token_for(long_url)).encode()) <= 64


# #UFB-0051
@pytest.mark.parametrize(
    "data,expected",
    [
        ("rb:0123456789abcdef", "0123456789abcdef"),
        ("rb:", None),
        ("rb:xyz", None),
        ("other:0123456789abcdef", None),
        ("rb:0123456789abcdef:extra", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_callback(data, expected):
    assert reports.parse_callback(data) == expected


# #UFB-0051
def test_callback_data_round_trips():
    token = reports.token_for(URL)
    assert reports.parse_callback(reports.callback_data(token)) == token


# --- keyboard ---


# #UFB-0051
def test_keyboard_only_for_failure_replies():
    assert reports.keyboard_for("plain text") is None
    assert reports.keyboard_for(None) is None
    markup = reports.keyboard_for(reports.FailureReply("x", URL, "failure"))
    button = markup.inline_keyboard[0][0]
    assert button.text == messages.report("button")
    assert reports.parse_callback(button.callback_data) == reports.token_for(URL)


# #UFB-0051
def test_failure_reply_is_a_str():
    reply = reports.FailureReply("hello", URL, "fallback_mirror")
    assert isinstance(reply, str)
    assert reply == "hello"
    assert (reply.url, reply.reason) == (URL, "fallback_mirror")


# #UFB-0051
def test_pending_table_is_bounded(monkeypatch):
    monkeypatch.setattr(reports, "MAX_PENDING", 3)
    for i in range(5):
        _token(f"https://example.org/{i}")
    assert reports.submit(1, reports.token_for("https://example.org/0")) == "expired"
    assert reports.submit(1, reports.token_for("https://example.org/4")) == "thanks"


# --- fallbacks carry the report data (UFB-0013) ---


@pytest.fixture
def fail_download(monkeypatch):
    from app.download import UnsupportedUrlError

    async def boom(url):
        raise UnsupportedUrlError("nope")

    monkeypatch.setattr("app.url_processing.follow_redirects", lambda url: url)
    monkeypatch.setattr("app.url_processing.attempt_download", boom)


# #UFB-0051, #UFB-0013
@pytest.mark.asyncio
async def test_mirror_fallback_is_failure_reply_with_reason(fail_download):
    result = await process_url_request(URL)
    assert isinstance(result, reports.FailureReply)
    assert (result.url, result.reason) == (URL, "fallback_mirror")
    assert result == messages.download_failed_mirror(
        "https://tfxktok.com/@u/video/1", URL
    )


# #UFB-0051, #UFB-0013
@pytest.mark.asyncio
async def test_plain_failure_is_failure_reply_with_reason(fail_download):
    url = "https://example.org/video"
    result = await process_url_request(url)
    assert isinstance(result, reports.FailureReply)
    assert (result.url, result.reason) == (url, "failure")


# #UFB-0051
@pytest.mark.asyncio
async def test_successful_reply_is_not_a_failure_reply(monkeypatch):
    from app.url_processing import DownloadResult

    async def ok(url):
        return DownloadResult(text="ok", media_path=None)

    monkeypatch.setattr("app.url_processing.follow_redirects", lambda url: url)
    monkeypatch.setattr("app.url_processing.attempt_download", ok)
    result = await process_url_request(URL)
    assert not isinstance(result, reports.FailureReply)


# --- submit: record, duplicate, rate limit, expiry ---


# #UFB-0051
def test_submit_logs_url_reason_platform_without_user_id(caplog):
    token = _token()
    with caplog.at_level(logging.WARNING, logger="app.reports"):
        assert reports.submit(424242, token) == "thanks"
    line = caplog.records[-1].getMessage()
    assert f"url={URL}" in line and "reason=failure" in line
    assert "platform=tiktok" in line
    assert "424242" not in line


# #UFB-0051, #UFB-0041
def test_submit_annotates_metadata_record_keeping_existing_keys():
    metadata.write(url_to_filename_stem(URL), {"title": "T", "saved_at": "x"})
    assert reports.submit(1, _token()) == "thanks"
    record = metadata.lookup(URL)
    assert record["title"] == "T"
    [entry] = record["reports"]
    assert entry["reason"] == "failure" and entry["platform"] == "tiktok"
    assert "user" not in entry


# #UFB-0051, #UFB-0041
def test_submit_creates_record_when_none_and_caps_list(monkeypatch):
    monkeypatch.setattr(settings, "REPORT_RATE_LIMIT", 0)
    token = _token()
    for user in range(1, 40):
        reports.submit(user, token)
    assert len(metadata.lookup(URL)["reports"]) == reports.MAX_RECORD_REPORTS


# #UFB-0051
def test_same_user_same_link_is_duplicate_and_not_recorded():
    token = _token()
    assert reports.submit(1, token) == "thanks"
    assert reports.submit(1, token) == "duplicate"
    assert len(metadata.lookup(URL)["reports"]) == 1


# #UFB-0051
def test_rate_limit_per_user_then_other_user_unaffected():
    tokens = [_token(f"https://example.org/{i}") for i in range(4)]
    assert [reports.submit(1, t) for t in tokens[:3]] == ["thanks"] * 3
    assert reports.submit(1, tokens[3]) == "limited"
    assert metadata.lookup("https://example.org/3") is None
    assert reports.submit(2, tokens[3]) == "thanks"
    assert metadata.lookup("https://example.org/3")["reports"]


# #UFB-0051
def test_rate_limit_window_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(reports.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(settings, "REPORT_RATE_LIMIT", 1)
    a, b = _token("https://example.org/a"), _token("https://example.org/b")
    assert reports.submit(1, a) == "thanks"
    assert reports.submit(1, b) == "limited"
    now[0] += settings.REPORT_RATE_WINDOW + 1
    assert reports.submit(1, b) == "thanks"


# #UFB-0051
def test_rate_limit_zero_disables_limit(monkeypatch):
    monkeypatch.setattr(settings, "REPORT_RATE_LIMIT", 0)
    for i in range(10):
        assert reports.submit(1, _token(f"https://example.org/{i}")) == "thanks"


# #UFB-0051
def test_unknown_token_is_expired():
    assert reports.submit(1, "0123456789abcdef") == "expired"


# --- callback handler ---


def make_query(data, user_id=7):
    query = MagicMock()
    query.data = data
    query.from_user.id = user_id
    query.answer = AsyncMock()
    return query


# #UFB-0051
def test_callback_handler_is_registered():
    assert any(h.callback is report_broken_link for h in dp.callback_query.handlers)


# #UFB-0051
@pytest.mark.asyncio
async def test_callback_stores_report_and_acknowledges():
    token = _token()
    query = make_query(reports.callback_data(token))
    await report_broken_link(query)
    query.answer.assert_awaited_once_with(messages.report("thanks"))
    assert metadata.lookup(URL)["reports"][0]["reason"] == "failure"


# #UFB-0051
@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["duplicate", "limited", "expired"])
async def test_callback_answers_each_outcome(kind, monkeypatch):
    monkeypatch.setattr(reports, "submit", lambda user, token: kind)
    query = make_query("rb:0123456789abcdef")
    await report_broken_link(query)
    query.answer.assert_awaited_once_with(messages.report(kind))


# #UFB-0051
@pytest.mark.asyncio
async def test_callback_with_bad_data_just_answers():
    query = make_query("rb:garbage")
    await report_broken_link(query)
    query.answer.assert_awaited_once_with(messages.report("expired"))
