from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptChunk:
    index: int
    start: float
    end: float
    text: str
    cue_indexes: list[int]


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

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration"] = self.duration
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

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration"] = self.duration
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
