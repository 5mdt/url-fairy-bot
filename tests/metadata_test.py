# metadata_test.py

import json
import os

import pytest

from app import metadata
from app.config import settings


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path))
    return tmp_path


# --- paths ---


# #UFB-0041
def test_meta_path_accepts_stem_or_media_filename(cache_dir):
    expected = str(cache_dir / "meta" / "clip.json")
    assert metadata.meta_path("clip") == expected
    assert metadata.meta_path("clip.mp4") == expected
    assert metadata.meta_path("/x/y/clip.mp4") == expected


# --- trimming ---


# #UFB-0041
def test_trim_info_keeps_only_agreed_fields():
    info = {
        "title": "T",
        "uploader": "U",
        "uploader_url": "https://u",
        "description": "D",
        "extractor_key": "Youtube",
        "duration": 12,
        "formats": [{"url": "x"}] * 50,
        "http_headers": {"a": "b"},
        "uploader_avatar": "https://cdn/a.jpg",
    }
    rec = metadata.trim_info(info, source_url="https://src", subtitles=["a.en.vtt"])
    assert rec["title"] == "T"
    assert rec["uploader"] == "U"
    assert rec["description"] == "D"
    assert rec["avatar_url"] == "https://cdn/a.jpg"
    assert rec["subtitles"] == ["a.en.vtt"]
    assert rec["source_url"] == "https://src"
    assert rec["extractor"] == "Youtube"
    assert "formats" not in rec and "http_headers" not in rec
    assert rec["saved_at"]


# #UFB-0041
def test_trim_info_tolerates_missing_keys_and_non_dicts():
    assert metadata.trim_info({}) is None
    assert metadata.trim_info(None) is None
    assert metadata.trim_info("nope") is None
    assert metadata.trim_info({"title": "only"})["title"] == "only"


# #UFB-0041
def test_trim_info_takes_first_playlist_entry():
    rec = metadata.trim_info({"entries": [None, {"title": "first"}]})
    assert rec["title"] == "first"


# #UFB-0041
def test_trim_info_caps_description_length():
    rec = metadata.trim_info({"title": "t", "description": "x" * 100000})
    assert len(rec["description"]) <= metadata.MAX_DESCRIPTION_CHARS


# #UFB-0041, #UFB-0039
def test_trim_tiktok_item_maps_author_and_description():
    item = {
        "desc": "caption #fyp",
        "author": {
            "nickname": "Nick",
            "uniqueId": "nick1",
            "avatarThumb": {"urlList": ["https://cdn/av.jpg"]},
        },
        "imagePost": {"images": [1, 2, 3]},
    }
    rec = metadata.trim_tiktok_item(item, source_url="https://tiktok.com/x")
    assert rec["title"] == "caption #fyp"
    assert rec["description"] == "caption #fyp"
    assert rec["uploader"] == "Nick"
    assert rec["avatar_url"] == "https://cdn/av.jpg"
    assert rec["source_url"] == "https://tiktok.com/x"
    assert "imagePost" not in rec


# #UFB-0041, #UFB-0039
def test_trim_tiktok_item_tolerates_empty():
    assert metadata.trim_tiktok_item({}) is None
    assert metadata.trim_tiktok_item({"author": None, "desc": "d"})["title"] == "d"


# --- store ---


# #UFB-0041
def test_write_read_round_trip(cache_dir):
    metadata.write("clip", {"title": "T", "custom": 1})
    assert metadata.read("clip.mp4") == {"title": "T", "custom": 1}
    assert json.loads((cache_dir / "meta" / "clip.json").read_text())["custom"] == 1
    assert not list((cache_dir / "meta").glob("*.tmp"))


# #UFB-0041
def test_read_missing_or_corrupt_is_none(cache_dir):
    assert metadata.read("nope") is None
    (cache_dir / "meta").mkdir()
    (cache_dir / "meta" / "bad.json").write_text("{not json")
    assert metadata.read("bad") is None
    (cache_dir / "meta" / "list.json").write_text("[1]")
    assert metadata.read("list") is None


# #UFB-0041
def test_write_none_is_noop(cache_dir):
    metadata.write("clip", None)
    assert metadata.read("clip") is None


# #UFB-0041
def test_lookup_by_url_uses_cache_stem():
    from app.download import url_to_filename_stem

    url = "https://example.com/v/1"
    metadata.write(url_to_filename_stem(url), {"title": "T"})
    assert metadata.lookup(url) == {"title": "T"}
    assert metadata.lookup("https://example.com/other") is None


# #UFB-0041
def test_delete_removes_record_and_is_idempotent(cache_dir):
    metadata.write("clip", {"title": "T"})
    assert metadata.delete("clip.mp4") is True
    assert metadata.read("clip") is None
    assert metadata.delete("clip") is False


# --- caption ---


# #UFB-0041
def test_caption_has_title_uploader_and_excerpt():
    html = metadata.caption(
        {"title": "My <video>", "uploader": "Bob", "description": "Line1\nLine2"},
        budget=500,
    )
    assert "<b>My &lt;video&gt;</b>" in html
    assert "Bob" in html
    assert "<i>Line1 Line2</i>" in html


# #UFB-0041
def test_caption_without_record_or_fields_is_empty():
    assert metadata.caption(None, budget=500) == ""
    assert metadata.caption({}, budget=500) == ""
    assert metadata.caption({"title": "t"}, budget=0) == ""


# #UFB-0041
@pytest.mark.parametrize("budget", [40, 120, 400, 900])
def test_caption_never_exceeds_budget(budget):
    rec = {
        "title": "<&>" * 300,
        "uploader": '"quoted" & co ' * 50,
        "description": "<b>" * 2000,
    }
    assert len(metadata.caption(rec, budget=budget)) <= budget


# #UFB-0041
def test_caption_shrinks_excerpt_before_title():
    rec = {"title": "Short title", "uploader": "U", "description": "d" * 2000}
    long_form = metadata.caption(rec, budget=900)
    short_form = metadata.caption(rec, budget=60)
    assert "Short title" in short_form
    assert "<i>" not in short_form
    assert "<i>" in long_form


# #UFB-0041
def test_caption_clips_with_ellipsis():
    rec = {"title": "t", "description": "word " * 500}
    html = metadata.caption(rec, budget=400)
    assert "…" in html


# #UFB-0041
def test_subtitle_url_and_dir(cache_dir):
    assert metadata.subs_dir("clip.mp4") == str(cache_dir / "subs" / "clip")
    assert (
        metadata.subtitle_url("clip.mp4", "clip.en.vtt")
        == "https://example.test/subs/clip/clip.en.vtt"
    )
    assert os.path.basename(metadata.subs_dir("clip")) == "clip"
