# download_test.py

import os
import time
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp
import yt_dlp.utils

from app.config import settings
from app.download import (
    UnsupportedUrlError,
    _resolve_cookie_path,
    _write_merged_cookies,
    url_to_filename_stem,
    yt_dlp_download,
)

# --- url_to_filename_stem (#UFB-0016) ---


@pytest.mark.parametrize(
    "url,expected",
    [
        ("abc123", "abc123"),
        (
            "https://www.tiktok.com/@user/video/1",
            "https___www_tiktok_com__user_video_1",
        ),
        ("a b!c", "a_b_c"),
    ],
)
def test_url_to_filename_stem(url, expected):
    assert url_to_filename_stem(url) == expected


# --- _write_merged_cookies ---


def test_write_merged_cookies_writes_header(tmp_path):
    dest = tmp_path / "merged.txt"
    _write_merged_cookies(str(dest), [])
    assert dest.read_text(encoding="utf-8") == "# Netscape HTTP Cookie File\n"


def test_write_merged_cookies_concatenates_multiple_files(tmp_path):
    f1 = tmp_path / "cookies1.txt"
    f2 = tmp_path / "cookies2.txt"
    f1.write_text("domain1\tTRUE\t/\tFALSE\t0\tname1\tval1\n", encoding="utf-8")
    f2.write_text("domain2\tTRUE\t/\tFALSE\t0\tname2\tval2\n", encoding="utf-8")

    dest = tmp_path / "merged.txt"
    _write_merged_cookies(str(dest), [str(f1), str(f2)])

    content = dest.read_text(encoding="utf-8")
    assert "domain1" in content
    assert "domain2" in content


def test_write_merged_cookies_drops_hash_space_comments_keeps_httponly(tmp_path):
    src = tmp_path / "cookies.txt"
    src.write_text(
        "# Netscape HTTP Cookie File\n"
        "# This is a comment\n"
        "#HttpOnly_.example.com\tTRUE\t/\tFALSE\t0\tname\tval\n"
        "plain_cookie_line\n",
        encoding="utf-8",
    )

    dest = tmp_path / "merged.txt"
    _write_merged_cookies(str(dest), [str(src)])

    content = dest.read_text(encoding="utf-8")
    assert "This is a comment" not in content
    assert "#HttpOnly_.example.com" in content
    assert "plain_cookie_line" in content


def test_write_merged_cookies_skips_unreadable_file_without_raising(tmp_path):
    dest = tmp_path / "merged.txt"
    missing = tmp_path / "does_not_exist.txt"
    # Should not raise despite the source file not existing.
    _write_merged_cookies(str(dest), [str(missing)])
    assert dest.exists()


# --- _resolve_cookie_path ---


def test_resolve_cookie_path_jar_enabled_creates_then_reuses(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", True)
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    jar_path = os.path.join(str(tmp_path), "cookie_jar.txt")
    monkeypatch.setattr("app.download.COOKIE_JAR_PATH", jar_path)

    src = tmp_path / "cookies.txt"
    src.write_text("cookie_data\n", encoding="utf-8")

    path1, should_delete1 = _resolve_cookie_path([str(src)])
    assert path1 == jar_path
    assert should_delete1 is False
    assert os.path.exists(jar_path)

    mtime_before = os.path.getmtime(jar_path)
    path2, should_delete2 = _resolve_cookie_path([str(src)])
    assert path2 == jar_path
    assert should_delete2 is False
    assert os.path.getmtime(jar_path) == mtime_before  # not rewritten


def test_resolve_cookie_path_jar_disabled_creates_temp_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", False)

    src = tmp_path / "cookies.txt"
    src.write_text("cookie_data\n", encoding="utf-8")

    path, should_delete = _resolve_cookie_path([str(src)])
    try:
        assert should_delete is True
        assert os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


# --- yt_dlp_download ---


@pytest.mark.asyncio
async def test_yt_dlp_download_cache_hit_skips_download(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    url = "https://tiktok.com/@user/video/1"
    from app.download import url_to_filename_stem

    cached_path = os.path.join(str(tmp_path), f"{url_to_filename_stem(url)}.mp4")
    with open(cached_path, "w") as f:
        f.write("fake video data")

    with patch("app.download.yt_dlp.YoutubeDL") as mock_ydl:
        result = await yt_dlp_download(url)

    assert result == cached_path
    mock_ydl.assert_not_called()


@pytest.mark.asyncio
async def test_yt_dlp_download_cache_hit_resolves_real_extension(tmp_path, monkeypatch):
    """A cache hit finds whatever extension the file actually has on disk,
    not a hardcoded `.mp4` (#BUG-0015)."""
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    url = "https://tiktok.com/@user/video/1"
    from app.download import url_to_filename_stem

    cached_path = os.path.join(str(tmp_path), f"{url_to_filename_stem(url)}.webm")
    with open(cached_path, "w") as f:
        f.write("fake video data")

    with patch("app.download.yt_dlp.YoutubeDL") as mock_ydl:
        result = await yt_dlp_download(url)

    assert result == cached_path
    mock_ydl.assert_not_called()


@pytest.mark.asyncio
async def test_yt_dlp_download_outtmpl_and_remuxer_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    url = "https://tiktok.com/@user/video/1"
    from app.download import url_to_filename_stem

    mock_instance = MagicMock()

    def _fake_download(urls):
        stem = url_to_filename_stem(url)
        with open(os.path.join(str(tmp_path), f"{stem}.mp4"), "w") as f:
            f.write("fake video data")

    mock_instance.download.side_effect = _fake_download
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_instance

    with patch(
        "app.download.yt_dlp.YoutubeDL", return_value=mock_ydl
    ) as mock_ydl_class:
        result = await yt_dlp_download(url)

    ydl_opts = mock_ydl_class.call_args[0][0]
    assert ydl_opts["outtmpl"].endswith("%(ext)s")
    assert ydl_opts["merge_output_format"] == "mp4"
    assert result.endswith(".mp4")


@pytest.mark.asyncio
async def test_yt_dlp_download_normalizes_fresh_download_only(tmp_path, monkeypatch):
    """#UFB-0040: a fresh download is passed to normalize_if_quiet; a cache
    hit is not re-measured."""
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    url = "https://tiktok.com/@user/video/1"
    from app.download import url_to_filename_stem

    expected = os.path.join(str(tmp_path), f"{url_to_filename_stem(url)}.mp4")
    mock_instance = MagicMock()

    def _fake_download(urls):
        with open(expected, "w") as f:
            f.write("fake video data")

    mock_instance.download.side_effect = _fake_download
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_instance

    with (
        patch("app.download.yt_dlp.YoutubeDL", return_value=mock_ydl),
        patch("app.download.media.normalize_if_quiet") as mock_normalize,
    ):
        fresh = await yt_dlp_download(url)
        mock_normalize.assert_called_once_with(expected)

        mock_normalize.reset_mock()
        cached = await yt_dlp_download(url)
        mock_normalize.assert_not_called()

    assert fresh == cached == expected


@pytest.mark.asyncio
async def test_yt_dlp_download_cache_hit_refreshes_atime_not_mtime(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    url = "https://tiktok.com/@user/video/1"

    cached_path = os.path.join(str(tmp_path), f"{url_to_filename_stem(url)}.mp4")
    with open(cached_path, "w") as f:
        f.write("fake video data")

    old_stamp = time.time() - 10 * 86400
    os.utime(cached_path, (old_stamp, old_stamp))

    with patch("app.download.yt_dlp.YoutubeDL") as mock_ydl:
        await yt_dlp_download(url)

    mock_ydl.assert_not_called()
    st = os.stat(cached_path)
    assert st.st_atime > old_stamp
    assert st.st_mtime == pytest.approx(old_stamp, abs=1)


@pytest.mark.asyncio
async def test_yt_dlp_download_unsupported_url_maps_to_custom_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))

    mock_instance = MagicMock()
    mock_instance.download.side_effect = yt_dlp.DownloadError("Unsupported URL: foo")
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_instance

    with patch("app.download.yt_dlp.YoutubeDL", return_value=mock_ydl):
        with pytest.raises(UnsupportedUrlError):
            await yt_dlp_download("https://unsupported.example.com/x")


@pytest.mark.asyncio
async def test_yt_dlp_download_other_download_error_maps_to_runtime_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))

    mock_instance = MagicMock()
    mock_instance.download.side_effect = yt_dlp.DownloadError("network is unreachable")
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_instance

    with patch("app.download.yt_dlp.YoutubeDL", return_value=mock_ydl):
        with pytest.raises(RuntimeError):
            await yt_dlp_download("https://tiktok.com/@user/video/1")


@pytest.mark.asyncio
async def test_yt_dlp_download_postprocessing_error_maps_to_runtime_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))

    mock_instance = MagicMock()
    mock_instance.download.side_effect = yt_dlp.utils.PostProcessingError(
        "post-process failed"
    )
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_instance

    with patch("app.download.yt_dlp.YoutubeDL", return_value=mock_ydl):
        with pytest.raises(RuntimeError):
            await yt_dlp_download("https://tiktok.com/@user/video/1")


@pytest.mark.asyncio
async def test_yt_dlp_download_deletes_temp_cookie_file_on_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIE_JAR_ENABLED", False)

    cookie_file = tmp_path / "cookies1.txt"
    cookie_file.write_text("cookie_data\n", encoding="utf-8")

    mock_instance = MagicMock()
    mock_instance.download.side_effect = yt_dlp.DownloadError("boom")
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_instance

    created_paths = []
    original_resolve = _resolve_cookie_path

    def _tracking_resolve(cookie_files):
        path, should_delete = original_resolve(cookie_files)
        created_paths.append(path)
        return path, should_delete

    with (
        patch("app.download.yt_dlp.YoutubeDL", return_value=mock_ydl),
        patch("app.download._resolve_cookie_path", side_effect=_tracking_resolve),
    ):
        with pytest.raises(RuntimeError):
            await yt_dlp_download("https://tiktok.com/@user/video/1")

    assert created_paths, "expected _resolve_cookie_path to be called"
    assert not os.path.exists(created_paths[0])


# --- UFB-0039: TikTok photo galleries ---

PHOTO_URL = "https://www.tiktok.com/@user/photo/123"


@pytest.mark.parametrize(
    "url,expected",
    [
        (PHOTO_URL, True),
        ("https://tiktok.com/@some.user-1/photo/9", True),
        ("https://www.tiktok.com/@user/video/123", False),
        ("https://example.com/@user/photo/123", False),
    ],
)
def test_is_tiktok_photo_url(url, expected):
    from app.download import is_tiktok_photo_url

    assert is_tiktok_photo_url(url) is expected


def _fake_ydl(item):
    ydl = MagicMock()
    ydl.get_info_extractor.return_value._extract_web_data_and_status.return_value = (
        item,
        0,
    )
    ydl.urlopen.side_effect = lambda u: MagicMock(read=lambda: f"bytes:{u}".encode())
    ydl.__enter__.return_value = ydl
    return ydl


def _item(images=2, music="https://cdn/a.mp3"):
    return {
        "imagePost": {
            "images": [
                {"imageURL": {"urlList": [f"https://cdn/{i}.jpg"]}}
                for i in range(images)
            ]
        },
        "music": {"playUrl": music},
    }


@pytest.mark.asyncio
async def test_tiktok_gallery_download_writes_images_and_audio(tmp_path, monkeypatch):
    from app.download import tiktok_gallery_download

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path / "nocookies"))
    ydl = _fake_ydl(_item())
    with patch("app.download.yt_dlp.YoutubeDL", return_value=ydl):
        result = await tiktok_gallery_download(PHOTO_URL)

    assert [os.path.basename(p) for p in result.image_paths] == ["01.jpg", "02.jpg"]
    assert open(result.image_paths[0], "rb").read() == b"bytes:https://cdn/0.jpg"
    assert result.audio_path.endswith(".mp3")
    assert open(result.audio_path, "rb").read() == b"bytes:https://cdn/a.mp3"
    called_url = (
        ydl.get_info_extractor.return_value._extract_web_data_and_status.call_args.args[
            0
        ]
    )
    assert called_url == "https://www.tiktok.com/@user/video/123"


@pytest.mark.asyncio
async def test_tiktok_gallery_download_cache_hit_skips_network(tmp_path, monkeypatch):
    from app.download import tiktok_gallery_download

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path / "nocookies"))
    with patch("app.download.yt_dlp.YoutubeDL", return_value=_fake_ydl(_item())):
        first = await tiktok_gallery_download(PHOTO_URL)
    with patch("app.download.yt_dlp.YoutubeDL") as mock_cls:
        second = await tiktok_gallery_download(PHOTO_URL)
    mock_cls.assert_not_called()
    assert second == first


@pytest.mark.asyncio
async def test_tiktok_gallery_download_without_images_is_unsupported(
    tmp_path, monkeypatch
):
    from app.download import tiktok_gallery_download

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path / "nocookies"))
    with patch("app.download.yt_dlp.YoutubeDL", return_value=_fake_ydl({})):
        with pytest.raises(UnsupportedUrlError):
            await tiktok_gallery_download(PHOTO_URL)


@pytest.mark.asyncio
async def test_tiktok_gallery_download_without_music_has_no_audio(
    tmp_path, monkeypatch
):
    from app.download import tiktok_gallery_download

    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "COOKIES_DIR", str(tmp_path / "nocookies"))
    with patch(
        "app.download.yt_dlp.YoutubeDL", return_value=_fake_ydl(_item(music=""))
    ):
        result = await tiktok_gallery_download(PHOTO_URL)
    assert result.audio_path is None
    assert len(result.image_paths) == 2
