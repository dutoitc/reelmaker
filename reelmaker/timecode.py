from __future__ import annotations

import re

_TIME_RE = re.compile(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})(?:[,.](\d{1,3}))?")


def parse_timecode(value: str) -> float:
    """Parse HH:MM:SS,mmm / MM:SS.mmm into seconds."""
    value = value.strip()
    match = _TIME_RE.search(value)
    if not match:
        raise ValueError(f"Invalid timecode: {value!r}")
    hours_s, minutes_s, seconds_s, millis_s = match.groups()
    hours = int(hours_s or 0)
    minutes = int(minutes_s)
    seconds = int(seconds_s)
    millis = int((millis_s or "0").ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def format_srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_hms(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total = int(round(seconds))
    s = total % 60
    total //= 60
    m = total % 60
    h = total // 60
    return f"{h:02d}:{m:02d}:{s:02d}"
