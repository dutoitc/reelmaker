from __future__ import annotations

import html
import re
from pathlib import Path

from .models import SubtitleCue, TranscriptChunk
from .timecode import format_srt_time, parse_timecode

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TIME_LINE_RE = re.compile(r"(.+?)\s+-->\s+(.+)")


def clean_subtitle_text(text: str) -> str:
    text = html.unescape(text)
    text = _TAG_RE.sub("", text)
    text = text.replace("\ufeff", "")
    text = _WS_RE.sub(" ", text)
    return text.strip()


def load_subtitles(path: Path) -> list[SubtitleCue]:
    suffix = path.suffix.lower()
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    if suffix == ".vtt":
        return parse_vtt(raw)
    return parse_srt(raw)


def parse_srt(raw: str) -> list[SubtitleCue]:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", raw.strip())
    cues: list[SubtitleCue] = []
    index = 1
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        time_line_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_line_idx is None:
            continue
        match = _TIME_LINE_RE.search(lines[time_line_idx])
        if not match:
            continue
        try:
            start = parse_timecode(match.group(1))
            end = parse_timecode(match.group(2))
        except ValueError:
            continue
        text = clean_subtitle_text(" ".join(lines[time_line_idx + 1 :]))
        if text and end > start:
            cues.append(SubtitleCue(index=index, start=start, end=end, text=text))
            index += 1
    return cues


def parse_vtt(raw: str) -> list[SubtitleCue]:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"^WEBVTT.*?(?:\n\n|$)", "", raw, flags=re.DOTALL)
    blocks = re.split(r"\n\s*\n", raw.strip())
    cues: list[SubtitleCue] = []
    index = 1
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        time_line_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_line_idx is None:
            continue
        match = _TIME_LINE_RE.search(lines[time_line_idx])
        if not match:
            continue
        left = match.group(1).strip()
        right = match.group(2).split()[0].strip()
        try:
            start = parse_timecode(left)
            end = parse_timecode(right)
        except ValueError:
            continue
        text = clean_subtitle_text(" ".join(lines[time_line_idx + 1 :]))
        if text and end > start:
            cues.append(SubtitleCue(index=index, start=start, end=end, text=text))
            index += 1
    return cues


def write_srt(path: Path, cues: list[SubtitleCue]) -> None:
    lines: list[str] = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{format_srt_time(cue.start)} --> {format_srt_time(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def transcript_to_text(cues: list[SubtitleCue]) -> str:
    return "\n".join(
        f"[{format_srt_time(cue.start)} - {format_srt_time(cue.end)}] {cue.text}" for cue in cues
    )


def chunk_transcript(
    cues: list[SubtitleCue],
    *,
    target_seconds: int = 480,
    overlap_seconds: int = 20,
    max_chars: int = 22000,
) -> list[TranscriptChunk]:
    if not cues:
        return []

    chunks: list[TranscriptChunk] = []
    start_i = 0
    chunk_index = 1

    while start_i < len(cues):
        chunk_cues: list[SubtitleCue] = []
        start_time = cues[start_i].start
        end_i = start_i
        char_count = 0

        while end_i < len(cues):
            cue = cues[end_i]
            projected_duration = cue.end - start_time
            projected_chars = char_count + len(cue.text) + 40
            if chunk_cues and (projected_duration > target_seconds or projected_chars > max_chars):
                break
            chunk_cues.append(cue)
            char_count = projected_chars
            end_i += 1

        if not chunk_cues:
            break

        text = transcript_to_text(chunk_cues)
        chunks.append(
            TranscriptChunk(
                index=chunk_index,
                start=chunk_cues[0].start,
                end=chunk_cues[-1].end,
                text=text,
                cue_indexes=[cue.index for cue in chunk_cues],
            )
        )
        chunk_index += 1

        if end_i >= len(cues):
            break

        overlap_start_time = max(cues[end_i - 1].end - overlap_seconds, cues[start_i].start)
        next_start = end_i
        for i in range(end_i - 1, start_i, -1):
            if cues[i].start <= overlap_start_time:
                next_start = i
                break
        if next_start <= start_i:
            next_start = end_i
        start_i = next_start

    return chunks


def _duration(cue: SubtitleCue) -> float:
    return max(0.0, cue.end - cue.start)


def _overlap(a: SubtitleCue, b: SubtitleCue) -> float:
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def normalize_segment_cues(cues: list[SubtitleCue], *, segment_duration: float) -> list[SubtitleCue]:
    """Clean YouTube subtitle artefacts for burned captions.

    YouTube auto captions can sometimes produce long overlapping cues plus
    normal short cues. If burned as-is, FFmpeg/libass displays two subtitle
    layers at the same time, including one that remains on screen for the
    whole reel. This function keeps the short timeline and removes obvious
    overlay artefacts.
    """
    if not cues:
        return []

    sorted_cues = sorted(cues, key=lambda c: (c.start, c.end))

    # Drop very long overlay cues when shorter cues cover the same period.
    filtered: list[SubtitleCue] = []
    for cue in sorted_cues:
        cue_duration = _duration(cue)
        overlaps_shorter = [
            other
            for other in sorted_cues
            if other is not cue and _duration(other) < cue_duration * 0.75 and _overlap(cue, other) > 0.3
        ]
        if cue_duration > max(8.0, segment_duration * 0.45) and len(overlaps_shorter) >= 2:
            continue
        filtered.append(cue)

    # Merge consecutive duplicate captions.
    merged: list[SubtitleCue] = []
    for cue in filtered:
        if merged and cue.text == merged[-1].text and cue.start - merged[-1].end <= 0.4:
            previous = merged[-1]
            merged[-1] = SubtitleCue(previous.index, previous.start, max(previous.end, cue.end), previous.text)
        else:
            merged.append(cue)

    # Resolve remaining overlaps so libass displays only one changing caption.
    resolved: list[SubtitleCue] = []
    for cue in merged:
        if resolved and resolved[-1].end > cue.start:
            previous = resolved[-1]
            new_end = max(previous.start + 0.25, cue.start - 0.05)
            if new_end > previous.start:
                resolved[-1] = SubtitleCue(previous.index, previous.start, new_end, previous.text)
            else:
                resolved.pop()
        if cue.end - cue.start >= 0.25:
            resolved.append(cue)

    return [SubtitleCue(index=i, start=c.start, end=c.end, text=c.text) for i, c in enumerate(resolved, start=1)]


def cues_for_segment(cues: list[SubtitleCue], start: float, end: float) -> list[SubtitleCue]:
    selected: list[SubtitleCue] = []
    for cue in cues:
        if cue.end <= start or cue.start >= end:
            continue
        local_start = max(0.0, cue.start - start)
        local_end = min(end - start, cue.end - start)
        if local_end > local_start:
            selected.append(SubtitleCue(index=len(selected) + 1, start=local_start, end=local_end, text=cue.text))
    return normalize_segment_cues(selected, segment_duration=max(0.0, end - start))
