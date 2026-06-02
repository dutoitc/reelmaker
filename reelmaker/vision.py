from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(frozen=True)
class CropHint:
    crop_x: int | None = None
    reason: str = "center"


def detect_face_crop_hint(
    *,
    source_video: Path,
    start: float,
    duration: float,
    target_width: int = 1080,
    target_height: int = 1920,
    samples: int = 7,
) -> CropHint:
    """Return a static crop-x hint based on simple frontal-face detection.

    This is deliberately optional. If OpenCV is not installed, if the video
    cannot be opened, or if no face is detected, the renderer falls back to a
    centered crop. It detects faces, not full bodies.
    """
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception:
        return CropHint(None, "opencv_missing")

    cap = cv2.VideoCapture(str(source_video))
    if not cap.isOpened():
        return CropHint(None, "video_open_failed")

    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if source_width <= 0 or source_height <= 0:
        cap.release()
        return CropHint(None, "unknown_dimensions")

    cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        cap.release()
        return CropHint(None, "haar_missing")

    centers: list[float] = []
    safe_duration = max(0.1, duration)
    for i in range(samples):
        ratio = (i + 0.5) / samples
        timestamp_ms = max(0.0, start + safe_duration * ratio) * 1000.0
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
        if len(faces) == 0:
            continue
        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
        centers.append(float(x + w / 2.0))

    cap.release()
    if not centers:
        return CropHint(None, "no_face_detected")

    source_aspect = source_width / source_height
    target_aspect = target_width / target_height
    if source_aspect >= target_aspect:
        scaled_width = int(round(source_width * (target_height / source_height)))
    else:
        scaled_width = target_width

    max_crop_x = max(0, scaled_width - target_width)
    if max_crop_x <= 0:
        return CropHint(0, "no_horizontal_crop_needed")

    face_x_source = float(median(centers))
    face_x_scaled = face_x_source * (scaled_width / source_width)
    crop_x = int(round(face_x_scaled - target_width / 2.0))
    crop_x = max(0, min(max_crop_x, crop_x))
    return CropHint(crop_x, f"face_detected_{len(centers)}_samples")
