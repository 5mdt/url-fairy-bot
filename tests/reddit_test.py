# reddit_test.py

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from app import metadata, pages, reddit
from app.config import settings
from app.download import url_to_filename_stem

POST_URL = "https://www.reddit.com/r/deck/comments/abc123/a_title/"
COMMENT_URL = "https://www.reddit.com/r/deck/comments/abc123/comment/c0mm3nt/"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path / "cookies"))
    reddit.reset_token()
    return tmp_path


def _response(status=200, body=None, content=b"", content_type="image/jpeg"):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    if body is None:
        r.json.side_effect = ValueError("no json")
    r.content = content
    r.headers = {"Content-Type": content_type}
    return r


def _post(**over):
    post = {
        "title": "Big news",
        "author": "alice",
        "subreddit": "deck",
        "selftext": "",
        "score": 1234,
        "is_self": True,
    }
    post.update(over)
    return post


def _thread(post, comment=None):
    listing = [{"data": {"children": [{"kind": "t3", "data": post}]}}]
    children = [{"kind": "t1", "data": comment}] if comment else []
    listing.append({"data": {"children": children}})
    return listing


def _meta(url, **over):
    entry = {"status": "valid", "e": "Image", "s": {"u": url}, "p": []}
    entry.update(over)
    return entry


# --- parse_link ---


# #UFB-0057
@pytest.mark.parametrize(
    "url, expected",
    [
        (POST_URL, reddit.RedditLink("post", "deck", "abc123")),
        (
            "https://old.reddit.com/r/deck/comments/abc123/",
            reddit.RedditLink("post", "deck", "abc123"),
        ),
        (
            "https://reddit.com/comments/abc123",
            reddit.RedditLink("post", None, "abc123"),
        ),
        (
            "https://www.reddit.com/user/bob/comments/abc123/x/",
            reddit.RedditLink("post", "bob", "abc123"),
        ),
        (COMMENT_URL, reddit.RedditLink("comment", "deck", "abc123", "c0mm3nt")),
        (
            "https://www.reddit.com/r/deck/comments/abc123/a_title/c0mm3nt/",
            reddit.RedditLink("comment", "deck", "abc123", "c0mm3nt"),
        ),
        (
            "https://www.reddit.com/user/Nett00n/",
            reddit.RedditLink("profile", "Nett00n"),
        ),
        ("https://m.reddit.com/u/Nett00n", reddit.RedditLink("profile", "Nett00n")),
        (
            "https://www.reddit.com/r/Safe4Trans/",
            reddit.RedditLink("subreddit", "Safe4Trans"),
        ),
        (
            "https://np.reddit.com/r/Safe4Trans",
            reddit.RedditLink("subreddit", "Safe4Trans"),
        ),
    ],
)
def test_parse_link_recognises_each_kind(url, expected):
    assert reddit.parse_link(url) == expected


# #UFB-0057
@pytest.mark.parametrize(
    "url",
    [
        "https://www.reddit.com/",
        "https://www.reddit.com/r/deck/wiki/index",
        "https://www.reddit.com/r/deck/s/AbCdEf",
        "https://www.reddit.com/search?q=x",
        "https://www.reddit.com/user/bob/submitted",
        "https://evilreddit.com/r/deck/",
        "https://example.com/r/deck/",
        "ftp://www.reddit.com/r/deck/",
    ],
)
def test_parse_link_ignores_everything_else(url):
    assert reddit.parse_link(url) is None


# --- API access ---


# #UFB-0057
def test_oauth_token_is_fetched_cached_and_used(monkeypatch):
    monkeypatch.setattr(settings, "REDDIT_CLIENT_ID", "id")
    monkeypatch.setattr(settings, "REDDIT_CLIENT_SECRET", "secret")
    token = _response(body={"access_token": "tok", "expires_in": 3600})
    api = _response(body={"ok": 1})
    with (
        patch("requests.post", return_value=token) as post,
        patch("requests.get", return_value=api) as get,
    ):
        assert reddit._api_get("/user/x/about") == {"ok": 1}
        reddit._api_get("/user/x/about")
    assert post.call_count == 1
    assert post.call_args.kwargs["auth"] == ("id", "secret")
    url = get.call_args.args[0]
    assert url == "https://oauth.reddit.com/user/x/about"
    assert get.call_args.kwargs["headers"]["Authorization"] == "bearer tok"
    assert get.call_args.kwargs["headers"]["User-Agent"] == "url-fairy-bot/test"
    assert get.call_args.kwargs["params"]["raw_json"] == 1


# #UFB-0057
def test_oauth_refreshes_the_token_once_on_401(monkeypatch):
    monkeypatch.setattr(settings, "REDDIT_CLIENT_ID", "id")
    monkeypatch.setattr(settings, "REDDIT_CLIENT_SECRET", "secret")
    tokens = [
        _response(body={"access_token": "old", "expires_in": 3600}),
        _response(body={"access_token": "new", "expires_in": 3600}),
    ]
    answers = [_response(status=401, body={}), _response(body={"ok": 1})]
    with (
        patch("requests.post", side_effect=tokens),
        patch("requests.get", side_effect=answers) as get,
    ):
        assert reddit._api_get("/x") == {"ok": 1}
    assert get.call_args.kwargs["headers"]["Authorization"] == "bearer new"


# #UFB-0057
def test_failed_token_request_raises(monkeypatch):
    monkeypatch.setattr(settings, "REDDIT_CLIENT_ID", "id")
    monkeypatch.setattr(settings, "REDDIT_CLIENT_SECRET", "secret")
    with patch("requests.post", return_value=_response(status=401, body={})):
        with pytest.raises(reddit.RedditError):
            reddit._api_get("/x")


# #UFB-0057
def test_without_credentials_reddit_cookies_are_sent(tmp_path):
    cookies = tmp_path / "cookies"
    cookies.mkdir()
    (cookies / "cookies.txt").write_text(
        "# Netscape HTTP Cookie File\n"
        ".reddit.com\tTRUE\t/\tTRUE\t2000000000\treddit_session\tabc\n"
        ".youtube.com\tTRUE\t/\tTRUE\t2000000000\tSID\tnope\n",
        encoding="utf-8",
    )
    with patch("requests.get", return_value=_response(body={"ok": 1})) as get:
        reddit._api_get("/r/x/about")
    assert get.call_args.args[0] == "https://www.reddit.com/r/x/about.json"
    assert get.call_args.kwargs["cookies"] == {"reddit_session": "abc"}


# #UFB-0038, #UFB-0057
def test_cookie_jar_is_read_instead_of_the_files_when_enabled(tmp_path, monkeypatch):
    cookies = tmp_path / "cookies"
    cookies.mkdir()
    (cookies / "cookies.txt").write_text(
        "# Netscape HTTP Cookie File\n"
        ".reddit.com\tTRUE\t/\tTRUE\t2000000000\ttoken_v2\told\n",
        encoding="utf-8",
    )
    jar = tmp_path / "cookie_jar.txt"
    jar.write_text(
        "# Netscape HTTP Cookie File\n"
        ".reddit.com\tTRUE\t/\tTRUE\t2000000000\ttoken_v2\trefreshed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.download.COOKIE_JAR_PATH", str(jar))
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", True)
    assert reddit._cookies() == {"token_v2": "refreshed"}


# #UFB-0038, #UFB-0057
def test_unreadable_cookie_jar_falls_back_to_the_files(tmp_path, monkeypatch):
    cookies = tmp_path / "cookies"
    cookies.mkdir()
    (cookies / "cookies.txt").write_text(
        "# Netscape HTTP Cookie File\n"
        ".reddit.com\tTRUE\t/\tTRUE\t2000000000\ttoken_v2\told\n",
        encoding="utf-8",
    )
    jar = tmp_path / "cookie_jar.txt"
    jar.write_text("garbage, not a cookie file", encoding="utf-8")
    monkeypatch.setattr("app.download.COOKIE_JAR_PATH", str(jar))
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", True)
    assert reddit._cookies() == {"token_v2": "old"}


# #UFB-0038, #UFB-0057
def test_missing_cookie_jar_falls_back_to_the_files(tmp_path, monkeypatch):
    cookies = tmp_path / "cookies"
    cookies.mkdir()
    (cookies / "cookies.txt").write_text(
        "# Netscape HTTP Cookie File\n"
        ".reddit.com\tTRUE\t/\tTRUE\t2000000000\ttoken_v2\told\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.download.COOKIE_JAR_PATH", str(tmp_path / "none.txt"))
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", True)
    assert reddit._cookies() == {"token_v2": "old"}


# #UFB-0057
@pytest.mark.parametrize(
    "response",
    [
        _response(status=403, body={}),
        _response(status=404, body={}),
        _response(status=429, body={}),
        _response(body=None),
        _response(body={"error": 403, "reason": "private"}),
    ],
)
def test_unusable_answers_raise_reddit_error(response):
    with patch("requests.get", return_value=response):
        with pytest.raises(reddit.RedditError):
            reddit._api_get("/x")


# #UFB-0057
def test_network_errors_raise_reddit_error():
    with patch("requests.get", side_effect=requests.ConnectionError("down")):
        with pytest.raises(reddit.RedditError):
            reddit._api_get("/x")


# #UFB-0057
def test_reddit_error_is_an_unsupported_url_error():
    from app.download import UnsupportedUrlError

    assert issubclass(reddit.RedditError, UnsupportedUrlError)


# --- reading posts and comments ---


# #UFB-0057
def test_text_post_maps_to_record_and_section():
    post = _post(selftext="Hello\n\nworld")
    with patch.object(reddit, "_api_get", return_value=_thread(post)):
        fetched = reddit._fetch(reddit.parse_link(POST_URL), POST_URL)
    assert fetched.kind == "post"
    assert fetched.record["title"] == "Big news"
    assert fetched.record["uploader"] == "u/alice"
    assert fetched.record["uploader_url"] == "https://www.reddit.com/user/alice/"
    assert fetched.record["description"] == "Hello\n\nworld"
    assert fetched.record["subtitle"] == "r/deck · ⬆️ 1,234"
    assert fetched.record["reddit"] == "post"
    assert fetched.hls_url is None


# #UFB-0057
def test_deleted_author_has_no_profile_link():
    post = _post(author="[deleted]", selftext="x")
    with patch.object(reddit, "_api_get", return_value=_thread(post)):
        fetched = reddit._fetch(reddit.parse_link(POST_URL), POST_URL)
    assert "uploader_url" not in fetched.record


# #UFB-0057
def test_gallery_images_follow_gallery_order():
    post = _post(
        is_gallery=True,
        gallery_data={"items": [{"media_id": "b"}, {"media_id": "a"}]},
        media_metadata={
            "a": _meta("https://i.redd.it/a.jpg"),
            "b": _meta("https://i.redd.it/b.jpg"),
            "c": _meta("https://i.redd.it/c.jpg", status="failed"),
        },
    )
    with patch.object(reddit, "_api_get", return_value=_thread(post)):
        fetched = reddit._fetch(reddit.parse_link(POST_URL), POST_URL)
    assert [i.url for i in fetched.sections[0].images] == [
        "https://i.redd.it/b.jpg",
        "https://i.redd.it/a.jpg",
    ]


# #UFB-0057
def test_animated_gallery_item_is_its_largest_still():
    entry = {
        "status": "valid",
        "e": "AnimatedImage",
        "s": {"gif": "https://i.redd.it/x.gif", "mp4": "https://i.redd.it/x.mp4"},
        "p": [
            {"u": "https://preview.redd.it/small.png"},
            {"u": "https://preview.redd.it/big.png"},
        ],
    }
    assert reddit._meta_urls(entry) == ("https://preview.redd.it/big.png", None)


# #UFB-0057
def test_image_keeps_its_preview_as_fallback():
    entry = _meta("https://i.redd.it/a.png", p=[{"u": "https://preview.redd.it/p.jpg"}])
    assert reddit._meta_urls(entry) == (
        "https://i.redd.it/a.png",
        "https://preview.redd.it/p.jpg",
    )


# #UFB-0057
def test_single_image_post_uses_its_url():
    post = _post(post_hint="image", url="https://i.redd.it/one.jpg", is_self=False)
    with patch.object(reddit, "_api_get", return_value=_thread(post)):
        fetched = reddit._fetch(reddit.parse_link(POST_URL), POST_URL)
    assert [i.url for i in fetched.sections[0].images] == ["https://i.redd.it/one.jpg"]


# #UFB-0057
def test_inline_images_become_markers_in_order():
    post = _post(
        selftext="Intro\n![img](two)\nmiddle ![img](one) end ![gif](giphy|zzz)",
        media_metadata={
            "one": _meta("https://i.redd.it/1.jpg"),
            "two": _meta("https://i.redd.it/2.jpg"),
        },
    )
    with patch.object(reddit, "_api_get", return_value=_thread(post)):
        fetched = reddit._fetch(reddit.parse_link(POST_URL), POST_URL)
    section = fetched.sections[0]
    assert [i.key for i in section.images] == ["two", "one"]
    assert section.body.index("[[img:two]]") < section.body.index("[[img:one]]")
    assert "giphy" not in section.body
    assert "[[img" not in fetched.record["description"]


# #UFB-0057
def test_video_post_exposes_its_hls_url():
    post = _post(
        is_video=True,
        is_self=False,
        secure_media={
            "reddit_video": {"hls_url": "https://v.redd.it/x/HLSPlaylist.m3u8"}
        },
    )
    with patch.object(reddit, "_api_get", return_value=_thread(post)):
        fetched = reddit._fetch(reddit.parse_link(POST_URL), POST_URL)
    assert fetched.hls_url == "https://v.redd.it/x/HLSPlaylist.m3u8"


# #UFB-0057
def test_crosspost_takes_media_and_text_from_its_source():
    source = _post(
        selftext="from source",
        is_gallery=True,
        gallery_data={"items": [{"media_id": "a"}]},
        media_metadata={"a": _meta("https://i.redd.it/a.jpg")},
    )
    post = _post(selftext="", crosspost_parent_list=[source])
    with patch.object(reddit, "_api_get", return_value=_thread(post)):
        fetched = reddit._fetch(reddit.parse_link(POST_URL), POST_URL)
    assert fetched.sections[0].body == "from source"
    assert [i.url for i in fetched.sections[0].images] == ["https://i.redd.it/a.jpg"]


# #UFB-0057
def test_comment_shows_the_comment_then_the_original_post():
    comment = {
        "author": "bob",
        "subreddit": "deck",
        "body": "nice ![img](m1)",
        "media_metadata": {"m1": _meta("https://i.redd.it/c.jpg")},
    }
    post = _post(
        post_hint="image", url="https://i.redd.it/p.jpg", is_self=False, selftext="orig"
    )
    with patch.object(reddit, "_api_get", return_value=_thread(post, comment)) as api:
        fetched = reddit._fetch(reddit.parse_link(COMMENT_URL), COMMENT_URL)
    assert api.call_args.kwargs["comment"] == "c0mm3nt"
    assert fetched.kind == "comment"
    assert fetched.record["title"] == "Re: Big news"
    assert fetched.record["uploader"] == "u/bob"
    assert fetched.record["description"] == "nice"
    first, second = fetched.sections
    assert first.images[0].album is True
    assert second.heading == "Original post"
    assert second.images[0].album is False
    assert second.body == "orig"


# #UFB-0057
def test_missing_comment_raises():
    with patch.object(reddit, "_api_get", return_value=_thread(_post())):
        with pytest.raises(reddit.RedditError):
            reddit._fetch(reddit.parse_link(COMMENT_URL), COMMENT_URL)


# #UFB-0057
def test_malformed_post_payload_raises():
    with patch.object(reddit, "_api_get", return_value={"nope": 1}):
        with pytest.raises(reddit.RedditError):
            reddit._fetch(reddit.parse_link(POST_URL), POST_URL)


# --- profiles and subreddits ---


PROFILE_URL = "https://www.reddit.com/user/Nett00n/"
SUB_URL = "https://www.reddit.com/r/Safe4Trans/"


# #UFB-0057
def test_profile_card_fields():
    about = {
        "data": {
            "name": "Nett00n",
            "total_karma": 12345,
            "created_utc": 1425168000,
            "icon_img": "https://styles.redditmedia.com/a.png",
            "subreddit": {
                "title": "Vlad",
                "public_description": "I make bots",
                "banner_img": "https://styles.redditmedia.com/b.png",
            },
        }
    }
    with patch.object(reddit, "_api_get", return_value=about):
        fetched = reddit._fetch(reddit.parse_link(PROFILE_URL), PROFILE_URL)
    assert fetched.kind == "profile"
    assert fetched.record["title"] == "Vlad"
    assert fetched.record["uploader"] == "u/Nett00n"
    assert fetched.record["description"] == "I make bots"
    assert fetched.record["subtitle"] == "⭐ 12,345 karma · 🎂 2015-03-01"
    assert fetched.sections[0].avatar.album is True
    assert fetched.banner.album is False


# #UFB-0057
def test_suspended_profile_raises():
    about = {"data": {"name": "x", "is_suspended": True}}
    with patch.object(reddit, "_api_get", return_value=about):
        with pytest.raises(reddit.RedditError):
            reddit._fetch(reddit.parse_link(PROFILE_URL), PROFILE_URL)


# #UFB-0057
def test_subreddit_card_fields():
    about = {
        "data": {
            "display_name": "Safe4Trans",
            "title": "Safe for Trans",
            "public_description": "A safe place",
            "description": "A safe place\n\nRules: be kind",
            "subscribers": 5000,
            "created_utc": 1425168000,
            "over18": True,
            "community_icon": "https://styles.redditmedia.com/i.png",
        }
    }
    with patch.object(reddit, "_api_get", return_value=about):
        fetched = reddit._fetch(reddit.parse_link(SUB_URL), SUB_URL)
    assert fetched.kind == "subreddit"
    assert fetched.record["uploader"] == "r/Safe4Trans"
    assert fetched.record["uploader_url"] == "https://www.reddit.com/r/Safe4Trans/"
    assert fetched.record["subtitle"] == "👥 5,000 members · 🎂 2015-03-01 · 🔞 NSFW"
    assert "Rules" in fetched.sections[0].body
    assert fetched.record["description"] == "A safe place"


# --- storing ---


def _fetched_post(images):
    section = reddit._Section(
        title="Big news",
        author="u/alice",
        body="text\n\n[[img:a]]",
        images=images,
    )
    record = {"title": "Big news", "uploader": "u/alice", "reddit": "post"}
    return reddit._Fetched("post", record, "Big news", [section])


# #UFB-0057
@pytest.mark.asyncio
async def test_download_caches_images_page_and_record(cache_dir):
    fetched = _fetched_post([reddit._Img("a", "https://i.redd.it/a.jpg")])
    fake = _response(content=b"jpgdata")
    with (
        patch.object(reddit, "_fetch", return_value=fetched),
        patch("requests.get", return_value=fake),
    ):
        result = await reddit.reddit_download(POST_URL)
        stem = url_to_filename_stem(POST_URL)
        assert result.image_paths == [str(cache_dir / "gallery" / stem / "01.jpg")]
        assert open(result.image_paths[0], "rb").read() == b"jpgdata"
        page = open(pages.reddit_page_path(stem), encoding="utf-8").read()
        assert f"https://example.test/gallery/{stem}/01.jpg" in page
        assert metadata.read(stem)["images"] == ["01.jpg"]

    # second call: served from the cache, no API call
    with patch.object(reddit, "_fetch", side_effect=AssertionError("refetched")):
        again = await reddit.reddit_download(POST_URL)
    assert again.image_paths == result.image_paths


# #UFB-0057
@pytest.mark.asyncio
async def test_oversized_image_falls_back_to_its_preview(cache_dir):
    big = _response(content=b"x" * (reddit._MAX_IMAGE_BYTES + 1))
    small = _response(content=b"small", content_type="image/png")
    image = reddit._Img("a", "https://i.redd.it/a.png", "https://preview.redd.it/p.png")
    fetched = _fetched_post([image])
    with (
        patch.object(reddit, "_fetch", return_value=fetched),
        patch("requests.get", side_effect=[big, small]),
    ):
        result = await reddit.reddit_download(POST_URL)
    assert result.image_paths[0].endswith("01.png")


# #UFB-0057
@pytest.mark.asyncio
async def test_failed_images_are_skipped_but_the_post_still_works(cache_dir):
    fetched = _fetched_post([reddit._Img("a", "https://i.redd.it/a.gif")])
    gif = _response(content=b"gif", content_type="image/gif")
    with (
        patch.object(reddit, "_fetch", return_value=fetched),
        patch("requests.get", return_value=gif),
    ):
        result = await reddit.reddit_download(POST_URL)
    assert result.image_paths == []
    assert os.path.exists(pages.reddit_page_path(url_to_filename_stem(POST_URL)))


# #UFB-0057
@pytest.mark.asyncio
async def test_album_images_are_numbered_before_page_only_ones(cache_dir):
    comment = reddit._Section(
        title="c", body="x", images=[reddit._Img("m", "https://i.redd.it/c.jpg")]
    )
    original = reddit._Section(
        title="p",
        body="y",
        images=[reddit._Img("p", "https://i.redd.it/p.jpg", album=False)],
    )
    fetched = reddit._Fetched(
        "comment", {"title": "Re: p", "reddit": "comment"}, "t", [comment, original]
    )
    seen = []

    def get(url, **kwargs):
        seen.append(url)
        return _response(content=b"img")

    with (
        patch.object(reddit, "_fetch", return_value=fetched),
        patch("requests.get", side_effect=get),
    ):
        result = await reddit.reddit_download(COMMENT_URL)
    assert seen == ["https://i.redd.it/c.jpg", "https://i.redd.it/p.jpg"]
    assert [os.path.basename(p) for p in result.image_paths] == ["01.jpg"]


# #UFB-0057
@pytest.mark.asyncio
async def test_video_post_downloads_the_hls_url_under_the_post_stem(cache_dir):
    fetched = _fetched_post([])
    fetched.hls_url = "https://v.redd.it/x/HLSPlaylist.m3u8"
    stem = url_to_filename_stem(POST_URL)
    with (
        patch.object(reddit, "_fetch", return_value=fetched),
        patch.object(
            reddit, "yt_dlp_download", new=AsyncMock(return_value="/c/video.mp4")
        ) as ytdlp,
    ):
        result = await reddit.reddit_download(POST_URL)
    ytdlp.assert_awaited_once_with(fetched.hls_url, stem=stem)
    assert result.video_path == "/c/video.mp4"
    assert metadata.read(stem)["reddit"] == "post"
    assert metadata.read(stem)["hls_url"] == fetched.hls_url


# #UFB-0057
@pytest.mark.asyncio
async def test_unparseable_link_raises():
    with pytest.raises(reddit.RedditError):
        await reddit.reddit_download("https://www.reddit.com/r/deck/wiki/x")
