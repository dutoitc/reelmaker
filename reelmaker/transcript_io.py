from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import (
    TRANSCRIPT_SCHEMA_VERSION,
    SubtitleCue,
    TranscriptDocument,
    TranscriptWord,
)
from .subtitles import transcript_to_text, write_srt
from .utils import read_json, write_json

_SAMPLE_SIZE = 1024 * 1024


def fingerprint_file(path: Path) -> str:
    """Create a fast content fingerprint suitable for large local media files.

    The hash covers file size plus samples from the start, middle, and end. It
    intentionally avoids reading a multi-gigabyte video in full on every run.
    """
    resolved = path.resolve()
    size = resolved.stat().st_size
    digest = hashlib.sha256()
    digest.update(str(size).encode("ascii"))

    with resolved.open("rb") as handle:
        offsets = [0]
        if size > _SAMPLE_SIZE * 2:
            offsets.append(max(0, size // 2 - _SAMPLE_SIZE // 2))
        if size > _SAMPLE_SIZE:
            offsets.append(max(0, size - _SAMPLE_SIZE))

        for offset in dict.fromkeys(offsets):
            handle.seek(offset)
            digest.update(str(offset).encode("ascii"))
            digest.update(handle.read(_SAMPLE_SIZE))

    return f"sha256-sampled:{digest.hexdigest()}"


def fingerprint_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def fingerprint_settings(settings: dict[str, Any]) -> str:
    canonical = json.dumps(settings, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return fingerprint_text(canonical)


def transcript_document_from_dict(data: Any) -> TranscriptDocument:
    if not isinstance(data, dict):
        raise ValueError("Transcript JSON root must be an object")
    if int(data.get("schema_version", 0)) != TRANSCRIPT_SCHEMA_VERSION:
        raise ValueError("Unsupported transcript schema version")

    raw_cues = data.get("cues")
    raw_words = data.get("words", [])
    if not isinstance(raw_cues, list) or not isinstance(raw_words, list):
        raise ValueError("Transcript cues and words must be lists")

    cues = [
        SubtitleCue(
            index=int(item["index"]),
            start=float(item["start"]),
            end=float(item["end"]),
            text=str(item["text"]),
        )
        for item in raw_cues
        if isinstance(item, dict)
    ]
    words = [
        TranscriptWord(
            index=int(item["index"]),
            cue_index=int(item["cue_index"]),
            start=float(item["start"]),
            end=float(item["end"]),
            text=str(item["text"]),
            score=float(item["score"]) if item.get("score") is not None else None,
            speaker=str(item["speaker"]) if item.get("speaker") is not None else None,
        )
        for item in raw_words
        if isinstance(item, dict)
    ]

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Transcript settings must be an object")

    return TranscriptDocument(
        schema_version=TRANSCRIPT_SCHEMA_VERSION,
        provider=str(data.get("provider") or "unknown"),
        language=str(data.get("language") or "unknown"),
        source=str(data.get("source") or ""),
        source_fingerprint=str(data.get("source_fingerprint") or ""),
        settings=settings,
        settings_fingerprint=str(data.get("settings_fingerprint") or ""),
        cues=cues,
        words=words,
    )


def read_transcript_document(path: Path) -> TranscriptDocument:
    return transcript_document_from_dict(read_json(path))


def write_transcript_outputs(output_dir: Path, document: TranscriptDocument) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "transcript.json"
    srt_path = output_dir / "transcript.srt"
    text_path = output_dir / "transcript.txt"

    write_json(json_path, document.to_dict())
    write_srt(srt_path, document.cues)
    text_path.write_text(transcript_to_text(document.cues), encoding="utf-8")
    return srt_path
