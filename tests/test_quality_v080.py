from pathlib import Path

from reelmaker.models import SubtitleCue
from reelmaker.renderer import (
    _cleanup_render_artifacts,
    _subtitle_ass_layout,
    _text_width_units,
    write_ass_subtitles,
)
from reelmaker.subtitle_corrector import correct_text_basic


def test_subtitle_layout_balances_lines_and_fits_safe_width():
    lines, font_size, scale_x = _subtitle_ass_layout(
        "C'est une plante qui produit du fourrage avec pas mal de protéines.",
        font_size=72,
        max_lines=2,
        safe_width_px=984,
    )

    assert 1 <= len(lines) <= 2
    assert font_size <= 72
    assert scale_x <= 100
    assert max(_text_width_units(line) * font_size * scale_x / 100 for line in lines) <= 984.5
    assert " ".join(lines) == "C'est une plante qui produit du fourrage avec pas mal de protéines."


def test_default_ass_uses_larger_text_and_narrow_safe_margins(tmp_path: Path):
    path = tmp_path / "subtitles.ass"
    write_ass_subtitles(
        path,
        [SubtitleCue(1, 0.0, 2.0, "Une plante bien connue chez nous.")],
    )
    raw = path.read_text(encoding="utf-8")

    assert "Style: Reel,Arial,72," in raw
    assert ",48,48,150,1" in raw
    assert "Une plante" in raw
    assert "chez nous." in raw


def test_successful_render_cleanup_removes_only_intermediates(tmp_path: Path):
    output = tmp_path / "R01.mp4"
    content = tmp_path / "R01_content.mp4"
    card = tmp_path / "R01_end_card.mp4"
    essential = tmp_path / "subtitles.srt"
    for path in (output, content, card, essential, tmp_path / "concat.txt", tmp_path / "end_card.ass"):
        path.write_bytes(b"x")

    _cleanup_render_artifacts(
        reel_dir=tmp_path,
        output_video=output,
        content_video=content,
        end_card_video=card,
        keep_intermediates=False,
    )

    assert output.exists()
    assert essential.exists()
    assert not content.exists()
    assert not card.exists()
    assert not (tmp_path / "concat.txt").exists()
    assert not (tmp_path / "end_card.ass").exists()


def test_cleanup_can_be_disabled_for_debugging(tmp_path: Path):
    output = tmp_path / "R01.mp4"
    content = tmp_path / "R01_content.mp4"
    card = tmp_path / "R01_end_card.mp4"
    for path in (output, content, card, tmp_path / "concat.txt", tmp_path / "end_card.ass"):
        path.write_bytes(b"x")

    _cleanup_render_artifacts(
        reel_dir=tmp_path,
        output_video=output,
        content_video=content,
        end_card_video=card,
        keep_intermediates=True,
    )

    assert content.exists()
    assert card.exists()
    assert (tmp_path / "concat.txt").exists()
    assert (tmp_path / "end_card.ass").exists()


def test_basic_correction_repairs_dangling_relative_clause():
    text = "Elle a des racines pivotantes qui vont très profond dans le sol, qui permet de faire comme un sous-solage."
    assert correct_text_basic(text) == (
        "Elle a des racines pivotantes qui vont très profond dans le sol, "
        "ce qui permet de faire comme un sous-solage."
    )
