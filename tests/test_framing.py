from pathlib import Path

from reelmaker.framing import build_framing_plan
from reelmaker.scene_analysis import Scene
from reelmaker.vision import CropHint


def test_static_smart_crop_uses_one_decision():
    calls = []

    def fake_crop(**kwargs):
        calls.append(kwargs)
        return CropHint(120, "face", 0.8)

    plan = build_framing_plan(
        source_video=Path("video.mp4"),
        start=10.0,
        end=20.0,
        crop_mode="smart",
        crop_detector=fake_crop,
    )

    assert len(plan) == 1
    assert plan[0].crop_hint.crop_x == 120
    assert calls[0]["duration"] == 10.0
    assert calls[0]["mode"] == "smart"


def test_scene_smart_crops_each_shot_and_merges_similar_crops():
    scenes = [Scene(1, 0.0, 5.0), Scene(2, 5.0, 10.0), Scene(3, 10.0, 15.0)]

    def fake_crop(**kwargs):
        start = kwargs["start"]
        if start < 5.0:
            return CropHint(100, "face", 0.9)
        if start < 10.0:
            return CropHint(118, "face", 0.8)
        return CropHint(500, "landscape", 0.6)

    plan = build_framing_plan(
        source_video=Path("video.mp4"),
        start=2.0,
        end=12.0,
        crop_mode="scene-smart",
        scenes=scenes,
        crop_detector=fake_crop,
        merge_tolerance=32,
    )

    assert len(plan) == 2
    assert (plan[0].start, plan[0].end) == (2.0, 10.0)
    assert plan[0].crop_hint.reason == "merged_adjacent_scenes"
    assert plan[0].crop_hint.crop_x == 111
    assert (plan[1].start, plan[1].end) == (10.0, 12.0)
    assert plan[1].crop_hint.crop_x == 500


def test_scene_smart_falls_back_to_full_interval_without_scene_list():
    def fake_crop(**kwargs):
        return CropHint(None, "center_fallback", 0.0)

    plan = build_framing_plan(
        source_video=Path("video.mp4"),
        start=3.0,
        end=7.0,
        crop_mode="scene-smart",
        scenes=None,
        crop_detector=fake_crop,
    )

    assert len(plan) == 1
    assert (plan[0].start, plan[0].end) == (3.0, 7.0)
