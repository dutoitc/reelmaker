from pathlib import Path

from reelmaker.youtube import _best_subtitle_file


def test_best_subtitle_prefers_useful_french_srt_over_tiny_placeholders(tmp_path: Path):
    tiny = tmp_path / "video.fr-CH.srt"
    tiny.write_text("empty\n", encoding="utf-8")

    useful = tmp_path / "video.fr.srt"
    useful.write_text("1\n00:00:01,000 --> 00:00:03,000\nBonjour Orbe\n\n" * 20, encoding="utf-8")

    english = tmp_path / "video.en.srt"
    english.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello Orbe\n\n" * 30, encoding="utf-8")

    assert _best_subtitle_file(tmp_path) == useful


def test_youtube_video_id_supports_common_url_forms():
    from reelmaker.youtube import _youtube_video_id

    assert _youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _youtube_video_id("https://youtu.be/dQw4w9WgXcQ?t=3") == "dQw4w9WgXcQ"
    assert _youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _youtube_video_id("https://example.com/watch?v=dQw4w9WgXcQ") is None


def test_best_subtitle_can_be_scoped_to_video_id(tmp_path: Path):
    first = tmp_path / "dQw4w9WgXcQ.fr.srt"
    first.write_text("first\n" * 100, encoding="utf-8")
    second = tmp_path / "abcdefghijk.fr.srt"
    second.write_text("second\n" * 200, encoding="utf-8")

    assert _best_subtitle_file(tmp_path, video_id="dQw4w9WgXcQ") == first
