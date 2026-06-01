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
