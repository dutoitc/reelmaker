from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .transcript_io import fingerprint_file, fingerprint_settings
from .utils import read_json, write_json


SCENE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Scene:
    index: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration"] = self.duration
        return data


@dataclass(frozen=True)
class SceneDocument:
    schema_version: int
    source: str
    source_fingerprint: str
    detector: str
    settings: dict[str, Any]
    settings_fingerprint: str
    scenes: list[Scene]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "source_fingerprint": self.source_fingerprint,
            "detector": self.detector,
            "settings": self.settings,
            "settings_fingerprint": self.settings_fingerprint,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }


SceneDetector = Callable[[Path, float, int], list[Scene]]


def detect_content_scenes(source_video: Path, threshold: float, min_scene_len: int) -> list[Scene]:
    """Detect shot boundaries with PySceneDetect's content detector.

    PySceneDetect is imported lazily so transcription-only and SRT workflows do
    not load OpenCV or require the optional vision dependencies.
    """
    try:
        from scenedetect import ContentDetector, detect  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "PySceneDetect is not installed. Activate the project environment and run: "
            'pip install -e ".[vision]"'
        ) from exc

    raw_scenes = detect(
        str(source_video),
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
        show_progress=False,
        start_in_scene=True,
    )
    scenes: list[Scene] = []
    for index, (start, end) in enumerate(raw_scenes, start=1):
        start_seconds = float(start.get_seconds())
        end_seconds = float(end.get_seconds())
        if end_seconds <= start_seconds:
            continue
        scenes.append(Scene(index=index, start=start_seconds, end=end_seconds))
    return scenes


def scene_document_from_dict(data: Any) -> SceneDocument:
    if not isinstance(data, dict):
        raise ValueError("Scene JSON root must be an object")
    if int(data.get("schema_version", 0)) != SCENE_SCHEMA_VERSION:
        raise ValueError("Unsupported scene schema version")

    raw_scenes = data.get("scenes")
    settings = data.get("settings")
    if not isinstance(raw_scenes, list):
        raise ValueError("Scene list must be an array")
    if not isinstance(settings, dict):
        raise ValueError("Scene settings must be an object")

    scenes = [
        Scene(
            index=int(item["index"]),
            start=float(item["start"]),
            end=float(item["end"]),
        )
        for item in raw_scenes
        if isinstance(item, dict) and float(item.get("end", 0.0)) > float(item.get("start", 0.0))
    ]
    return SceneDocument(
        schema_version=SCENE_SCHEMA_VERSION,
        source=str(data.get("source") or ""),
        source_fingerprint=str(data.get("source_fingerprint") or ""),
        detector=str(data.get("detector") or "content"),
        settings=settings,
        settings_fingerprint=str(data.get("settings_fingerprint") or ""),
        scenes=scenes,
    )


def read_scene_document(path: Path) -> SceneDocument:
    return scene_document_from_dict(read_json(path))


def load_or_detect_scenes(
    source_video: Path,
    output_dir: Path,
    *,
    threshold: float = 27.0,
    min_scene_len: int = 15,
    force: bool = False,
    detector: SceneDetector = detect_content_scenes,
) -> tuple[SceneDocument, bool]:
    """Load a valid scene cache or detect scenes and persist it.

    Returns ``(document, reused_cache)``.
    """
    if not source_video.exists():
        raise RuntimeError(f"Source video not found: {source_video}")
    if min_scene_len < 1:
        raise RuntimeError("Scene minimum length must be at least one frame")
    if threshold <= 0:
        raise RuntimeError("Scene threshold must be greater than zero")

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / "scenes.json"
    source_fingerprint = fingerprint_file(source_video)
    settings = {
        "detector": "content",
        "threshold": float(threshold),
        "min_scene_len": int(min_scene_len),
    }
    settings_fingerprint = fingerprint_settings(settings)

    if cache_path.exists() and not force:
        try:
            cached = read_scene_document(cache_path)
            if (
                cached.source_fingerprint == source_fingerprint
                and cached.settings_fingerprint == settings_fingerprint
                and cached.detector == "content"
            ):
                return cached, True
        except (OSError, ValueError, KeyError, TypeError):
            pass

    scenes = detector(source_video, float(threshold), int(min_scene_len))
    document = SceneDocument(
        schema_version=SCENE_SCHEMA_VERSION,
        source=str(source_video.resolve()),
        source_fingerprint=source_fingerprint,
        detector="content",
        settings=settings,
        settings_fingerprint=settings_fingerprint,
        scenes=scenes,
    )
    write_json(cache_path, document.to_dict())
    return document, False


def scenes_for_range(scenes: list[Scene], start: float, end: float) -> list[Scene]:
    """Clip detected scenes to a source interval and fill uncovered gaps.

    Gaps can appear when the source interval starts before the first detected
    scene or ends after the final one. Returning a complete timeline keeps the
    framing plan deterministic.
    """
    if end <= start:
        return []

    clipped: list[Scene] = []
    cursor = start
    for scene in sorted(scenes, key=lambda item: (item.start, item.end)):
        scene_start = max(start, scene.start)
        scene_end = min(end, scene.end)
        if scene_end <= scene_start:
            continue
        if scene_start > cursor + 0.001:
            clipped.append(Scene(index=len(clipped) + 1, start=cursor, end=scene_start))
        clipped.append(Scene(index=len(clipped) + 1, start=max(cursor, scene_start), end=scene_end))
        cursor = max(cursor, scene_end)
        if cursor >= end:
            break

    if cursor < end - 0.001:
        clipped.append(Scene(index=len(clipped) + 1, start=cursor, end=end))
    if not clipped:
        clipped.append(Scene(index=1, start=start, end=end))
    return clipped
