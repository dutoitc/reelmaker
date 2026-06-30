from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TextBandScores:
    top: float
    middle: float
    bottom: float
    total: float
    frames: int

    @property
    def has_text(self) -> bool:
        return self.total >= 0.12

    @property
    def preferred_subtitle_position(self) -> str:
        # Existing subtitles and lower thirds are usually in the bottom band.
        # Choose the less occupied safe band, but keep bottom when no text is detected.
        if not self.has_text:
            return "bottom"
        if self.bottom > self.top * 1.15 or self.bottom >= 0.11:
            return "top"
        if self.top > self.bottom * 1.15:
            return "bottom"
        return "top" if self.top <= self.bottom else "bottom"


def _sample_video_frames(source_video: Path, *, start: float, duration: float, samples: int):
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception:
        return [], None

    cap = cv2.VideoCapture(str(source_video))
    if not cap.isOpened():
        return [], cv2
    frames = []
    safe_duration = max(0.1, duration)
    for index in range(max(2, samples)):
        ratio = (index + 0.5) / max(2, samples)
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, start + safe_duration * ratio) * 1000.0)
        ok, frame = cap.read()
        if ok and frame is not None:
            frames.append(frame)
    cap.release()
    return frames, cv2


def detect_visual_text(
    *,
    source_video: Path,
    start: float,
    duration: float,
    samples: int = 7,
) -> TextBandScores:
    frames, cv2 = _sample_video_frames(source_video, start=start, duration=duration, samples=samples)
    if not frames or cv2 is None:
        return TextBandScores(0.0, 0.0, 0.0, 0.0, 0)
    return score_text_bands(frames, cv2=cv2)


def score_text_bands(frames: list, *, cv2=None) -> TextBandScores:
    if cv2 is None:
        try:
            import cv2  # type: ignore[import-not-found]
        except Exception:
            return TextBandScores(0.0, 0.0, 0.0, 0.0, 0)

    top_scores: list[float] = []
    middle_scores: list[float] = []
    bottom_scores: list[float] = []
    totals: list[float] = []

    for frame in frames:
        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            continue
        target_width = 640
        scale = min(1.0, target_width / width)
        if scale < 1.0:
            frame = cv2.resize(frame, (target_width, max(1, int(round(height * scale)))))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # Text creates many short vertical strokes. Sobel-X plus a horizontal
        # closing kernel groups letters into words while excluding tall objects
        # such as pillars or railings.
        grad = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
        _, binary = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        closed = cv2.dilate(closed, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 2)), iterations=1)

        frame_height, frame_width = gray.shape[:2]
        mask = gray.copy()
        mask[:] = 0
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < frame_width * frame_height * 0.00035:
                continue
            if w < frame_width * 0.035 or w > frame_width * 0.98:
                continue
            if h < max(5, frame_height * 0.012) or h > frame_height * 0.38:
                continue
            if w / max(1, h) < 1.55:
                continue
            fill = cv2.countNonZero(binary[y : y + h, x : x + w]) / max(1, area)
            if fill < 0.04 or fill > 0.72:
                continue
            cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)

        def band_score(y0: float, y1: float) -> float:
            top = int(frame_height * y0)
            bottom = max(top + 1, int(frame_height * y1))
            band = mask[top:bottom]
            occupancy = cv2.countNonZero(band) / max(1, band.size)
            return min(1.0, occupancy * 7.0)

        top = band_score(0.02, 0.34)
        middle = band_score(0.30, 0.70)
        bottom = band_score(0.66, 0.98)
        total = min(1.0, max(top, middle, bottom) + (top + middle + bottom) * 0.18)
        top_scores.append(top)
        middle_scores.append(middle)
        bottom_scores.append(bottom)
        totals.append(total)

    if not totals:
        return TextBandScores(0.0, 0.0, 0.0, 0.0, 0)

    # Use a high percentile-like average so text visible on several sampled
    # frames is retained without one noisy frame dominating the decision.
    def robust(values: list[float]) -> float:
        ordered = sorted(values, reverse=True)
        count = max(1, min(3, len(ordered)))
        return sum(ordered[:count]) / count

    return TextBandScores(
        round(robust(top_scores), 4),
        round(robust(middle_scores), 4),
        round(robust(bottom_scores), 4),
        round(robust(totals), 4),
        len(totals),
    )
