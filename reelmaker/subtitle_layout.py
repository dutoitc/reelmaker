from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .models import SubtitleCue


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    centiseconds = int(round(seconds * 100))
    cs = centiseconds % 100
    total_seconds = centiseconds // 100
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("\\", "\\\\")
    text = text.replace("{", r"\{").replace("}", r"\}")
    return text


def _text_width_units(text: str) -> float:
    """Approximate Arial glyph width in font-size units."""
    units = 0.0
    for char in text:
        if char.isspace():
            units += 0.30
        elif char in "ilI.,:;!'’|()[]":
            units += 0.28
        elif char in "mwMW@#%&QO0":
            units += 0.86
        elif char.isupper():
            units += 0.66
        else:
            units += 0.54
    return units


def _best_line_partition(words: tuple[str, ...], line_count: int) -> list[str]:
    if not words:
        return []
    line_count = max(1, min(line_count, len(words)))

    @lru_cache(maxsize=None)
    def solve(start: int, remaining: int) -> tuple[float, tuple[str, ...]]:
        if remaining == 1:
            line = " ".join(words[start:])
            return _text_width_units(line), (line,)

        best: tuple[float, tuple[str, ...]] | None = None
        max_end = len(words) - remaining + 1
        for end in range(start + 1, max_end + 1):
            line = " ".join(words[start:end])
            rest_width, rest_lines = solve(end, remaining - 1)
            score = max(_text_width_units(line), rest_width)
            candidate = (score, (line, *rest_lines))
            if best is None or candidate[0] < best[0]:
                best = candidate
        assert best is not None
        return best

    return list(solve(0, line_count)[1])


def _subtitle_ass_layout(
    text: str,
    *,
    font_size: int,
    max_lines: int,
    safe_width_px: int,
) -> tuple[list[str], int, int]:
    """Balance subtitle lines and fit them inside the horizontal safe area."""
    escaped = _ass_escape(text)
    words = tuple(escaped.split())
    if not words:
        return [], font_size, 100

    max_lines = max(1, max_lines)
    requested_units = safe_width_px / max(1, font_size)
    if _text_width_units(escaped) <= requested_units:
        lines = [escaped]
    else:
        lines = _best_line_partition(words, min(max_lines, len(words)))

    longest = max(_text_width_units(line) for line in lines)
    effective_size = min(font_size, int(safe_width_px / max(0.1, longest)))
    effective_size = max(32, effective_size)
    rendered_width = longest * effective_size
    scale_x = 100
    if rendered_width > safe_width_px:
        scale_x = max(55, min(100, int(100 * safe_width_px / rendered_width)))
    return lines, effective_size, scale_x


def write_ass_subtitles(
    path: Path,
    cues: list[SubtitleCue],
    *,
    font_size: int = 72,
    margin_v: int = 150,
    wrap_width: int = 30,
    max_lines: int = 2,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    position: str = "bottom",
) -> None:
    """Write large, balanced ASS subtitles without horizontal overflow.

    ``wrap_width`` remains part of the public API because it controls upstream
    cue splitting. Final line balancing uses estimated rendered width instead
    of blindly counting characters.
    """
    del wrap_width
    alignment = 8 if position == "top" else 2
    margin_h = 48
    safe_width_px = max(200, play_res_x - 2 * margin_h)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,5,1,{alignment},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header.rstrip()]
    for cue in cues:
        wrapped_lines, effective_size, scale_x = _subtitle_ass_layout(
            cue.text,
            font_size=font_size,
            max_lines=max_lines,
            safe_width_px=safe_width_px,
        )
        if not wrapped_lines:
            continue
        overrides: list[str] = []
        if effective_size != font_size:
            overrides.append(rf"\fs{effective_size}")
        if scale_x != 100:
            overrides.append(rf"\fscx{scale_x}")
        prefix = "{" + "".join(overrides) + "}" if overrides else ""
        text = prefix + r"\N".join(wrapped_lines)
        lines.append(f"Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},Reel,,0,0,0,,{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
