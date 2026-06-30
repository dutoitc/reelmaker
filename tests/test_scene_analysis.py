from pathlib import Path

import pytest

from reelmaker.scene_analysis import (
    SCENE_SCHEMA_VERSION,
    Scene,
    load_or_detect_scenes,
    scene_document_from_dict,
    scenes_for_range,
)


def test_scene_document_from_dict():
    document = scene_document_from_dict(
        {
            "schema_version": SCENE_SCHEMA_VERSION,
            "source": "video.mp4",
            "source_fingerprint": "fingerprint",
            "detector": "content",
            "settings": {"threshold": 27.0, "min_scene_len": 15},
            "settings_fingerprint": "settings",
            "scenes": [
                {"index": 1, "start": 0.0, "end": 4.5},
                {"index": 2, "start": 4.5, "end": 9.0},
            ],
        }
    )

    assert len(document.scenes) == 2
    assert document.scenes[0].duration == 4.5


def test_scene_document_rejects_unknown_schema():
    with pytest.raises(ValueError, match="schema version"):
        scene_document_from_dict({"schema_version": 99, "settings": {}, "scenes": []})


def test_load_or_detect_scenes_reuses_fingerprinted_cache(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video-content")
    output = tmp_path / "output"
    calls: list[tuple[float, int]] = []

    def fake_detector(_source: Path, threshold: float, min_scene_len: int) -> list[Scene]:
        calls.append((threshold, min_scene_len))
        return [Scene(1, 0.0, 8.0)]

    first, reused_first = load_or_detect_scenes(source, output, detector=fake_detector)
    second, reused_second = load_or_detect_scenes(source, output, detector=fake_detector)

    assert not reused_first
    assert reused_second
    assert first.scenes == second.scenes
    assert calls == [(27.0, 15)]
    assert (output / "scenes.json").exists()


def test_scene_cache_invalidates_when_settings_change(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video-content")
    output = tmp_path / "output"
    calls = 0

    def fake_detector(_source: Path, _threshold: float, _min_scene_len: int) -> list[Scene]:
        nonlocal calls
        calls += 1
        return [Scene(1, 0.0, 8.0)]

    load_or_detect_scenes(source, output, threshold=27.0, detector=fake_detector)
    load_or_detect_scenes(source, output, threshold=22.0, detector=fake_detector)

    assert calls == 2


def test_scenes_for_range_clips_and_fills_gaps():
    scenes = [Scene(1, 1.0, 4.0), Scene(2, 5.0, 9.0)]

    clipped = scenes_for_range(scenes, 2.0, 8.0)

    assert [(scene.start, scene.end) for scene in clipped] == [
        (2.0, 4.0),
        (4.0, 5.0),
        (5.0, 8.0),
    ]
