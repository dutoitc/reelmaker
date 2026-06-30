from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .scene_analysis import Scene, scenes_for_range
from .vision import CropHint, detect_smart_crop_hint


@dataclass(frozen=True)
class FramingSegment:
    start: float
    end: float
    crop_hint: CropHint

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, object]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "crop_x": self.crop_hint.crop_x,
            "reason": self.crop_hint.reason,
            "confidence": round(self.crop_hint.confidence, 3),
        }


CropDetector = Callable[..., CropHint]


def build_framing_plan(
    *,
    source_video: Path,
    start: float,
    end: float,
    crop_mode: str,
    scenes: list[Scene] | None = None,
    crop_detector: CropDetector = detect_smart_crop_hint,
    merge_tolerance: int = 32,
) -> list[FramingSegment]:
    """Build static or per-shot crop decisions without rendering anything."""
    if end <= start:
        return []

    if crop_mode == "center":
        return [FramingSegment(start, end, CropHint(None, "center", 1.0))]

    if crop_mode in {"face", "motion", "smart"}:
        hint = crop_detector(
            source_video=source_video,
            start=start,
            duration=end - start,
            mode=crop_mode,
        )
        return [FramingSegment(start, end, hint)]

    if crop_mode != "scene-smart":
        raise ValueError(f"Unsupported crop mode: {crop_mode}")

    timeline = scenes_for_range(scenes or [], start, end)
    segments: list[FramingSegment] = []
    for scene in timeline:
        hint = crop_detector(
            source_video=source_video,
            start=scene.start,
            duration=scene.duration,
            mode="smart",
        )
        current = FramingSegment(scene.start, scene.end, hint)
        if segments and _can_merge(segments[-1], current, tolerance=merge_tolerance):
            previous = segments[-1]
            merged_hint = _merge_hints(previous, current)
            segments[-1] = FramingSegment(previous.start, current.end, merged_hint)
        else:
            segments.append(current)
    return segments


def _can_merge(left: FramingSegment, right: FramingSegment, *, tolerance: int) -> bool:
    if abs(left.end - right.start) > 0.01:
        return False
    left_x = left.crop_hint.crop_x
    right_x = right.crop_hint.crop_x
    if left_x is None or right_x is None:
        return left_x is None and right_x is None
    return abs(left_x - right_x) <= tolerance


def _merge_hints(left: FramingSegment, right: FramingSegment) -> CropHint:
    left_x = left.crop_hint.crop_x
    right_x = right.crop_hint.crop_x
    if left_x is None or right_x is None:
        crop_x = None
    else:
        total = max(0.001, left.duration + right.duration)
        crop_x = int(round((left_x * left.duration + right_x * right.duration) / total))
    confidence = min(left.crop_hint.confidence, right.crop_hint.confidence)
    return CropHint(crop_x, "merged_adjacent_scenes", confidence)
