from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


TRANSCRIPT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptWord:
    index: int
    cue_index: int
    start: float
    end: float
    text: str
    score: float | None = None
    speaker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptionResult:
    language: str
    cues: list[SubtitleCue]
    words: list[TranscriptWord] = field(default_factory=list)


@dataclass(frozen=True)
class TranscriptDocument:
    schema_version: int
    provider: str
    language: str
    source: str
    source_fingerprint: str
    settings: dict[str, Any]
    settings_fingerprint: str
    cues: list[SubtitleCue]
    words: list[TranscriptWord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "language": self.language,
            "source": self.source,
            "source_fingerprint": self.source_fingerprint,
            "settings": self.settings,
            "settings_fingerprint": self.settings_fingerprint,
            "cues": [asdict(cue) for cue in self.cues],
            "words": [word.to_dict() for word in self.words],
        }


@dataclass(frozen=True)
class TranscriptChunk:
    index: int
    start: float
    end: float
    text: str
    cue_indexes: list[int]


@dataclass(frozen=True)
class ReelSegment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, float]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
        }


def normalize_segments(start: float, end: float, segments: list[ReelSegment] | None) -> list[ReelSegment]:
    valid = [segment for segment in (segments or []) if segment.end > segment.start]
    if valid:
        return valid
    if end > start:
        return [ReelSegment(start, end)]
    return []


@dataclass
class ReelCandidate:
    id: str
    start: float
    end: float
    title: str
    hook: str
    reason: str
    score: float
    transcript_excerpt: str
    source_chunk: int | None = None
    warnings: list[str] = field(default_factory=list)
    boundary_method: str | None = None
    boundary_score: float | None = None
    boundary_reasons: list[str] = field(default_factory=list)
    segments: list[ReelSegment] = field(default_factory=list)

    @property
    def source_segments(self) -> list[ReelSegment]:
        return normalize_segments(self.start, self.end, self.segments)

    @property
    def duration(self) -> float:
        return sum(segment.duration for segment in self.source_segments)

    @property
    def is_composite(self) -> bool:
        return len(self.source_segments) > 1

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["segments"] = [segment.to_dict() for segment in self.source_segments]
        data["duration"] = self.duration
        data["is_composite"] = self.is_composite
        return data


@dataclass
class ReelSelection:
    id: str
    candidate_id: str
    rank: int
    start: float
    end: float
    title: str
    hook: str
    reason: str
    transcript_excerpt: str
    segments: list[ReelSegment] = field(default_factory=list)

    @property
    def source_segments(self) -> list[ReelSegment]:
        return normalize_segments(self.start, self.end, self.segments)

    @property
    def duration(self) -> float:
        return sum(segment.duration for segment in self.source_segments)

    @property
    def is_composite(self) -> bool:
        return len(self.source_segments) > 1

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["segments"] = [segment.to_dict() for segment in self.source_segments]
        data["duration"] = self.duration
        data["is_composite"] = self.is_composite
        return data


@dataclass(frozen=True)
class ProjectPaths:
    output_dir: Path
    subtitles_dir: Path
    logs_dir: Path
    source_dir: Path

    @classmethod
    def create(cls, output_dir: Path) -> "ProjectPaths":
        output_dir.mkdir(parents=True, exist_ok=True)
        subtitles_dir = output_dir / "subtitles"
        logs_dir = output_dir / "logs"
        source_dir = output_dir / "source"
        subtitles_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)
        return cls(output_dir=output_dir, subtitles_dir=subtitles_dir, logs_dir=logs_dir, source_dir=source_dir)
