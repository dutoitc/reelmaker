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


def cues_for_segment(cues: list[SubtitleCue], start: float, end: float) -> list[SubtitleCue]:
    selected: list[SubtitleCue] = []
    for cue in cues:
        if cue.end <= start or cue.start >= end:
            continue
        local_start = max(0.0, cue.start - start)
        local_end = min(end - start, cue.end - start)
        if local_end > local_start:
            selected.append(SubtitleCue(index=len(selected) + 1, start=local_start, end=local_end, text=cue.text))
    return selected
