from reelmaker.renderer import _scale_crop_filter
from reelmaker.vision import CropHint


def test_fit_blur_layout_preserves_full_wide_frame():
    filter_value = _scale_crop_filter(CropHint(None, "wide", 0.8, "fit-blur"))

    assert "force_original_aspect_ratio=decrease" in filter_value
    assert "gblur" in filter_value
    assert "overlay" in filter_value
