from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

from .visual_text import score_text_bands


@dataclass(frozen=True)
class CropHint:
    crop_x: int | None = None
    reason: str = "center"
    confidence: float = 0.0
    layout: str = "crop"  # crop | fit-blur


def _scaled_width(source_width: int, source_height: int, *, target_width: int, target_height: int) -> int:
    source_aspect = source_width / source_height
    target_aspect = target_width / target_height
    if source_aspect >= target_aspect:
        return int(round(source_width * (target_height / source_height)))
    return target_width


def _crop_x_from_center(
    center_x_source: float,
    *,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> int:
    scaled_width = _scaled_width(source_width, source_height, target_width=target_width, target_height=target_height)
    max_crop_x = max(0, scaled_width - target_width)
    if max_crop_x <= 0:
        return 0
    center_x_scaled = center_x_source * (scaled_width / source_width)
    crop_x = int(round(center_x_scaled - target_width / 2.0))
    return max(0, min(max_crop_x, crop_x))


def _crop_x_for_span(
    min_x_source: float,
    max_x_source: float,
    *,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> int:
    """Choose a crop that tries to keep a horizontal span visible.

    Useful when two faces are close enough to fit in the 9:16 crop. If the span
    is wider than the crop, this still centers the group instead of hard-centering
    the full frame.
    """
    scaled_width = _scaled_width(source_width, source_height, target_width=target_width, target_height=target_height)
    max_crop_x = max(0, scaled_width - target_width)
    if max_crop_x <= 0:
        return 0
    scale = scaled_width / source_width
    min_scaled = min_x_source * scale
    max_scaled = max_x_source * scale
    span_center = (min_scaled + max_scaled) / 2.0
    crop_x = int(round(span_center - target_width / 2.0))
    return max(0, min(max_crop_x, crop_x))


def detect_face_crop_hint(
    *,
    source_video: Path,
    start: float,
    duration: float,
    target_width: int = 1080,
    target_height: int = 1920,
    samples: int = 9,
) -> CropHint:
    return detect_smart_crop_hint(
        source_video=source_video,
        start=start,
        duration=duration,
        target_width=target_width,
        target_height=target_height,
        samples=samples,
        mode="face",
    )


def detect_motion_crop_hint(
    *,
    source_video: Path,
    start: float,
    duration: float,
    target_width: int = 1080,
    target_height: int = 1920,
    samples: int = 12,
) -> CropHint:
    return detect_smart_crop_hint(
        source_video=source_video,
        start=start,
        duration=duration,
        target_width=target_width,
        target_height=target_height,
        samples=samples,
        mode="motion",
    )


def detect_smart_crop_hint(
    *,
    source_video: Path,
    start: float,
    duration: float,
    target_width: int = 1080,
    target_height: int = 1920,
    samples: int = 12,
    mode: str = "smart",
) -> CropHint:
    """Return a static 9:16 crop hint using faces first, then motion.

    This intentionally stays lightweight and local. It does not identify the
    active speaker from audio. It improves the common failure where a centered
    9:16 crop cuts out the interviewee or presenter.
    """
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except Exception:
        return CropHint(None, "opencv_or_numpy_missing", 0.0)

    cap = cv2.VideoCapture(str(source_video))
    if not cap.isOpened():
        return CropHint(None, "video_open_failed", 0.0)

    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if source_width <= 0 or source_height <= 0:
        cap.release()
        return CropHint(None, "unknown_dimensions", 0.0)

    safe_duration = max(0.1, duration)
    frames = []
    for i in range(max(2, samples)):
        ratio = (i + 0.5) / max(2, samples)
        timestamp_ms = max(0.0, start + safe_duration * ratio) * 1000.0
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
        ok, frame = cap.read()
        if ok and frame is not None:
            frames.append(frame)
    cap.release()

    if not frames:
        return CropHint(None, "no_frames", 0.0)

    # Preserve full-width title cards, lower thirds and already burned captions.
    # Cropping those frames destroys words even when a face or motion detector
    # would otherwise choose a narrow 9:16 region.
    text_scores = score_text_bands(frames, cv2=cv2)
    if mode == "smart" and text_scores.has_text and source_width / source_height > target_width / target_height:
        return CropHint(None, "embedded_text_preserved", min(1.0, text_scores.total), "fit-blur")

    if mode in {"face", "smart"}:
        face_hint = _detect_face_hint_from_frames(
            frames,
            cv2=cv2,
            source_width=source_width,
            source_height=source_height,
            target_width=target_width,
            target_height=target_height,
        )
        if mode == "face" or face_hint.crop_x is not None or face_hint.layout == "fit-blur":
            return face_hint

    # In automatic mode, a wide frame without a confidently detected face is
    # preserved. Camera movement is not enough evidence to crop away people,
    # scenery, title graphics, or contextual objects. Users can still request
    # --crop-mode motion explicitly.
    if mode == "smart" and source_width / source_height > target_width / target_height:
        return CropHint(None, "wide_without_reliable_face_preserved", 0.55, "fit-blur")

    if mode in {"motion", "smart"}:
        motion_hint = _detect_motion_hint_from_frames(
            frames,
            cv2=cv2,
            np=np,
            source_width=source_width,
            source_height=source_height,
            target_width=target_width,
            target_height=target_height,
        )
        if motion_hint.crop_x is not None and (mode == "motion" or motion_hint.confidence >= 0.55):
            return motion_hint

    if mode == "smart" and source_width / source_height > target_width / target_height:
        return CropHint(None, "wide_visual_preserved", 0.5, "fit-blur")
    return CropHint(None, "center_fallback", 0.0)


def _detect_face_hint_from_frames(
    frames: list,
    *,
    cv2,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> CropHint:
    cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        return CropHint(None, "haar_missing", 0.0)

    weighted_centers: list[float] = []
    frame_face_sets: list[list[tuple[int, int, int, int]]] = []
    frames_with_faces = 0

    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(36, 36))
        if len(faces) == 0:
            continue
        faces_sorted = sorted(faces, key=lambda rect: rect[2] * rect[3], reverse=True)[:3]
        largest_area = max(w * h for x, y, w, h in faces_sorted)
        relevant = [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces_sorted if (w * h) >= largest_area * 0.35]
        if not relevant:
            continue
        frame_face_sets.append(relevant)
        frames_with_faces += 1
        for x, _y, w, h in relevant:
            center = float(x + w / 2.0)
            weight = max(1, int(round((w * h) / max(1, largest_area) * 3)))
            weighted_centers.extend([center] * weight)

    if not weighted_centers:
        return CropHint(None, "no_face_detected", 0.0)

    confidence = min(1.0, frames_with_faces / max(1, len(frames)))
    multi_sets = [faces for faces in frame_face_sets if len(faces) >= 2]
    if multi_sets:
        representative = max(multi_sets, key=lambda faces: sum(w * h for _x, _y, w, h in faces))
        representative = sorted(representative, key=lambda rect: rect[2] * rect[3], reverse=True)
        largest_area = representative[0][2] * representative[0][3]
        second_area = representative[1][2] * representative[1][3]

        # If one face clearly dominates, isolate it. Otherwise preserve both
        # people with a blurred background instead of cutting both faces.
        if largest_area >= second_area * 1.8:
            x, _y, w, _h = representative[0]
            crop_x = _crop_x_from_center(
                x + w / 2.0,
                source_width=source_width,
                source_height=source_height,
                target_width=target_width,
                target_height=target_height,
            )
            return CropHint(crop_x, "dominant_face", confidence, "crop")
        # Two similarly important people are preserved in full. A narrow 9:16
        # crop is too fragile: it can cut shoulders, gestures or one face when
        # either person moves between samples.
        return CropHint(None, "two_person_shot_preserved", confidence, "fit-blur")

    center_x = float(median(weighted_centers))
    crop_x = _crop_x_from_center(
        center_x,
        source_width=source_width,
        source_height=source_height,
        target_width=target_width,
        target_height=target_height,
    )
    return CropHint(crop_x, f"face_{frames_with_faces}_samples", confidence, "crop")


def _detect_motion_hint_from_frames(
    frames: list,
    *,
    cv2,
    np,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> CropHint:
    if len(frames) < 2:
        return CropHint(None, "not_enough_frames_for_motion", 0.0)

    centers: list[float] = []
    weights: list[float] = []
    prev = None
    for frame in frames:
        small = cv2.resize(frame, (320, max(1, int(320 * source_height / source_width))))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)
        if prev is None:
            prev = gray
            continue
        diff = cv2.absdiff(prev, gray)
        prev = gray
        _, thresh = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        moments = cv2.moments(thresh)
        if moments["m00"] <= 1500:
            continue
        center_small = moments["m10"] / moments["m00"]
        center_source = center_small * (source_width / 320.0)
        centers.append(float(center_source))
        weights.append(float(moments["m00"]))

    if not centers:
        return CropHint(None, "no_motion_detected", 0.0)

    # Weighted median-like behaviour: duplicate only a few times to avoid huge lists.
    expanded: list[float] = []
    max_weight = max(weights)
    for center, weight in zip(centers, weights):
        expanded.extend([center] * max(1, int(round((weight / max_weight) * 5))))
    center_x = float(median(expanded or centers))
    crop_x = _crop_x_from_center(
        center_x,
        source_width=source_width,
        source_height=source_height,
        target_width=target_width,
        target_height=target_height,
    )
    confidence = min(1.0, len(centers) / max(1, len(frames) - 1))
    return CropHint(crop_x, f"motion_{len(centers)}_samples", confidence, "crop")
