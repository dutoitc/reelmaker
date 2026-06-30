from reelmaker.vision import CropHint


def test_crop_hint_defaults():
    hint = CropHint()
    assert hint.crop_x is None
    assert hint.reason == "center"
    assert hint.confidence == 0.0
