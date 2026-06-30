from __future__ import annotations

from dataclasses import dataclass

from .models import ReelCandidate, ReelSegment, SubtitleCue, TranscriptWord

_SENTENCE_ENDINGS = (".", "!", "?", "…")


@dataclass(frozen=True)
class BoundaryPoint:
    time: float
    score: float
    reasons: tuple[str, ...]
    available_silence: float


def refine_candidate_boundaries(
    candidates: list[ReelCandidate],
    cues: list[SubtitleCue],
    words: list[TranscriptWord] | None = None,
    *,
    mode: str = "auto",
    min_duration: int = 18,
    target_duration: int = 22,
    max_duration: int = 60,
    pre_padding: float = 0.25,
    post_padding: float = 1.2,
) -> list[ReelCandidate]:
    """Snap candidate cuts to natural speech boundaries.

    Composite candidates are refined segment by segment, then kept in their
    editorial order. A final cut strongly prefers punctuation or a measured
    pause so rendered reels do not stop in the middle of a sentence.
    """
    if not candidates or not cues or mode == "off":
        return candidates

    timed_words = _sorted_valid_words(words or [])
    use_words = mode in {"auto", "words"} and bool(timed_words)

    refined: list[ReelCandidate] = []
    for candidate in candidates:
        segments = candidate.source_segments
        if len(segments) <= 1:
            refined.extend(
                _refine_single_candidates(
                    [candidate],
                    cues,
                    timed_words,
                    use_words=use_words,
                    min_duration=min_duration,
                    target_duration=target_duration,
                    max_duration=max_duration,
                    pre_padding=pre_padding,
                    post_padding=post_padding,
                )
            )
            continue

        refined_segments: list[ReelSegment] = []
        segment_scores: list[float] = []
        reasons: list[str] = []
        per_segment_min = max(3, min(min_duration, 8))
        per_segment_target = max(per_segment_min, min(target_duration, 14))
        per_segment_max = max(per_segment_target, min(max_duration, 30))
        for index, segment in enumerate(segments, start=1):
            temporary = ReelCandidate(
                id=candidate.id,
                start=segment.start,
                end=segment.end,
                title=candidate.title,
                hook=candidate.hook,
                reason=candidate.reason,
                score=candidate.score,
                transcript_excerpt=candidate.transcript_excerpt,
            )
            result = _refine_single_candidates(
                [temporary],
                cues,
                timed_words,
                use_words=use_words,
                min_duration=per_segment_min,
                target_duration=per_segment_target,
                max_duration=per_segment_max,
                pre_padding=pre_padding,
                post_padding=post_padding,
            )[0]
            refined_segments.append(ReelSegment(result.start, result.end))
            if result.boundary_score is not None:
                segment_scores.append(result.boundary_score)
            reasons.extend(f"segment{index}:{reason}" for reason in result.boundary_reasons)

        candidate.segments = refined_segments
        candidate.start = refined_segments[0].start
        candidate.end = refined_segments[-1].end
        candidate.boundary_method = "segments"
        candidate.boundary_score = round(sum(segment_scores) / len(segment_scores), 1) if segment_scores else None
        candidate.boundary_reasons = reasons
        if "boundary_refined" not in candidate.warnings:
            candidate.warnings.append("boundary_refined")
        if candidate.duration < min_duration and "too_short" not in candidate.warnings:
            candidate.warnings.append("too_short")
        if candidate.duration > max_duration and "too_long" not in candidate.warnings:
            candidate.warnings.append("too_long")
        refined.append(candidate)

    return _remove_near_duplicates(refined)


def _refine_single_candidates(
    candidates: list[ReelCandidate],
    cues: list[SubtitleCue],
    timed_words: list[TranscriptWord],
    *,
    use_words: bool,
    min_duration: int,
    target_duration: int,
    max_duration: int,
    pre_padding: float,
    post_padding: float,
) -> list[ReelCandidate]:
    if use_words:
        return _refine_with_words(
            candidates,
            cues,
            timed_words,
            min_duration=min_duration,
            target_duration=target_duration,
            max_duration=max_duration,
            pre_padding=pre_padding,
            post_padding=post_padding,
        )
    return _refine_with_cues(
        candidates,
        cues,
        min_duration=min_duration,
        target_duration=target_duration,
        max_duration=max_duration,
        pre_padding=pre_padding,
        post_padding=post_padding,
    )


def _sorted_valid_words(words: list[TranscriptWord]) -> list[TranscriptWord]:
    return sorted(
        [word for word in words if word.end > word.start and word.text.strip()],
        key=lambda word: (word.start, word.end, word.index),
    )


def _refine_with_words(
    candidates: list[ReelCandidate],
    cues: list[SubtitleCue],
    words: list[TranscriptWord],
    *,
    min_duration: int,
    target_duration: int,
    max_duration: int,
    pre_padding: float,
    post_padding: float,
) -> list[ReelCandidate]:
    starts = _word_start_points(words)
    ends = _word_end_points(words)
    video_end = max(cue.end for cue in cues)
    refined: list[ReelCandidate] = []

    for candidate in candidates:
        original_start = candidate.start
        original_end = candidate.end

        start_point = _choose_start_point(starts, original_start, original_end)
        if start_point is None:
            refined.extend(
                _refine_with_cues(
                    [candidate],
                    cues,
                    min_duration=min_duration,
                    target_duration=target_duration,
                    max_duration=max_duration,
                    pre_padding=pre_padding,
                    post_padding=post_padding,
                )
            )
            continue

        new_start = max(0.0, start_point.time - min(pre_padding, start_point.available_silence))
        preferred_end = _preferred_end(
            original_end=original_end,
            new_start=new_start,
            min_duration=min_duration,
            target_duration=target_duration,
            max_duration=max_duration,
        )
        end_point = _choose_end_point(
            ends,
            original_end=original_end,
            new_start=new_start,
            preferred_end=preferred_end,
            min_duration=min_duration,
            max_duration=max_duration,
        )
        if end_point is None:
            refined.extend(
                _refine_with_cues(
                    [candidate],
                    cues,
                    min_duration=min_duration,
                    target_duration=target_duration,
                    max_duration=max_duration,
                    pre_padding=pre_padding,
                    post_padding=post_padding,
                )
            )
            continue

        new_end = min(video_end, end_point.time + min(post_padding, end_point.available_silence))
        if new_end - new_start > max_duration:
            new_end = new_start + max_duration

        candidate.start = round(new_start, 3)
        candidate.end = round(new_end, 3)
        candidate.boundary_method = "words"
        candidate.boundary_score = round((start_point.score + end_point.score) / 2.0, 1)
        candidate.boundary_reasons = [
            *(f"start:{reason}" for reason in start_point.reasons),
            *(f"end:{reason}" for reason in end_point.reasons),
        ]
        _mark_boundary_result(candidate, original_start, original_end, min_duration, max_duration)
        refined.append(candidate)

    return refined


def _word_start_points(words: list[TranscriptWord]) -> list[BoundaryPoint]:
    points: list[BoundaryPoint] = []
    for index, word in enumerate(words):
        previous = words[index - 1] if index > 0 else None
        reasons: list[str] = []
        score = 25.0

        if previous is None:
            gap = word.start
            score += 65.0
            reasons.append("transcript_start")
        else:
            gap = max(0.0, word.start - previous.end)
            score += _pause_score(gap)
            if gap >= 0.3:
                reasons.append(f"pause_{gap:.2f}s")
            if _is_sentence_end(previous.text):
                score += 20.0
                reasons.append("previous_sentence_end")
            if previous.cue_index != word.cue_index:
                score += 8.0
                reasons.append("cue_boundary")
            if previous.speaker and word.speaker and previous.speaker != word.speaker:
                score += 15.0
                reasons.append("speaker_change")

        points.append(
            BoundaryPoint(
                word.start,
                min(100.0, score),
                tuple(reasons or ["word_start"]),
                max(0.0, gap),
            )
        )
    return points


def _word_end_points(words: list[TranscriptWord]) -> list[BoundaryPoint]:
    points: list[BoundaryPoint] = []
    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else None
        reasons: list[str] = []
        score = 25.0

        if _is_sentence_end(word.text):
            score += 30.0
            reasons.append("sentence_end")

        if following is None:
            gap = float("inf")
            score += 65.0
            reasons.append("transcript_end")
        else:
            gap = max(0.0, following.start - word.end)
            score += _pause_score(gap)
            if gap >= 0.3:
                reasons.append(f"pause_{gap:.2f}s")
            if following.cue_index != word.cue_index:
                score += 8.0
                reasons.append("cue_boundary")
            if word.speaker and following.speaker and word.speaker != following.speaker:
                score += 15.0
                reasons.append("speaker_change")

        points.append(
            BoundaryPoint(
                word.end,
                min(100.0, score),
                tuple(reasons or ["word_end"]),
                max(0.0, gap),
            )
        )
    return points


def _pause_score(gap: float) -> float:
    if gap >= 1.0:
        return 45.0
    if gap >= 0.6:
        return 35.0
    if gap >= 0.3:
        return 20.0
    if gap >= 0.15:
        return 8.0
    return 0.0


def _choose_start_point(
    points: list[BoundaryPoint],
    original_start: float,
    original_end: float,
) -> BoundaryPoint | None:
    nearby = [
        point
        for point in points
        if original_start - 5.0 <= point.time <= original_start + 1.5
        and point.time < original_end - 0.5
    ]
    if not nearby:
        return None

    def utility(point: BoundaryPoint) -> float:
        distance = abs(point.time - original_start)
        late_penalty = max(0.0, point.time - original_start) * 18.0
        return point.score - distance * 7.0 - late_penalty

    return max(nearby, key=utility)


def _preferred_end(
    *,
    original_end: float,
    new_start: float,
    min_duration: int,
    target_duration: int,
    max_duration: int,
) -> float:
    duration = original_end - new_start
    if duration < min_duration:
        preferred = new_start + max(min_duration, target_duration)
    elif duration > max_duration:
        preferred = new_start + max_duration
    else:
        preferred = original_end
    return min(new_start + max_duration, preferred)


def _choose_end_point(
    points: list[BoundaryPoint],
    *,
    original_end: float,
    new_start: float,
    preferred_end: float,
    min_duration: int,
    max_duration: int,
) -> BoundaryPoint | None:
    minimum_end = new_start + min_duration
    maximum_end = new_start + max_duration
    nearby = [
        point
        for point in points
        if minimum_end <= point.time <= maximum_end
        and original_end - 2.0 <= point.time <= max(original_end + 10.0, preferred_end + 6.0)
    ]
    if not nearby:
        nearby = [point for point in points if minimum_end <= point.time <= maximum_end]
    if not nearby:
        return None

    complete = [
        point
        for point in nearby
        if "sentence_end" in point.reasons
        or "transcript_end" in point.reasons
        or point.available_silence >= 0.6
        or "speaker_change" in point.reasons
    ]
    pool = complete or nearby

    def utility(point: BoundaryPoint) -> float:
        distance = abs(point.time - preferred_end)
        early_penalty = max(0.0, original_end - point.time) * 22.0
        incomplete_penalty = 35.0 if point not in complete else 0.0
        return point.score - distance * 25.0 - early_penalty - incomplete_penalty

    return max(pool, key=utility)


def _refine_with_cues(
    candidates: list[ReelCandidate],
    cues: list[SubtitleCue],
    *,
    min_duration: int,
    target_duration: int,
    max_duration: int,
    pre_padding: float,
    post_padding: float,
) -> list[ReelCandidate]:
    refined: list[ReelCandidate] = []
    video_end = max(cue.end for cue in cues)

    for candidate in candidates:
        original_start = candidate.start
        original_end = candidate.end
        match = _overlapping_cue_indexes(cues, candidate.start, candidate.end)
        if match is None:
            refined.append(candidate)
            continue

        first, last = match
        new_start = max(0.0, cues[first].start - pre_padding)
        new_end = min(video_end, cues[last].end + post_padding)

        while last + 1 < len(cues) and (new_end - new_start) < min_duration:
            last += 1
            new_end = min(video_end, cues[last].end + post_padding)

        while last + 1 < len(cues) and (new_end - new_start) < target_duration:
            if _is_sentence_end(cues[last].text) and (new_end - new_start) >= min_duration:
                break
            next_end = min(video_end, cues[last + 1].end + post_padding)
            if next_end - new_start > max_duration:
                break
            last += 1
            new_end = next_end

        # Never stop on an obviously unfinished cue when a natural end is nearby.
        while last + 1 < len(cues) and not _cue_is_complete_end(cues, last):
            next_end = min(video_end, cues[last + 1].end + post_padding)
            if next_end - new_start > max_duration:
                break
            last += 1
            new_end = next_end

        if first > 0 and (new_end - new_start) < target_duration:
            previous = cues[first - 1]
            if cues[first].start - previous.end <= 1.5:
                possible_start = max(0.0, previous.start - pre_padding)
                if new_end - possible_start <= max_duration:
                    first -= 1
                    new_start = possible_start

        candidate.start = round(new_start, 3)
        candidate.end = round(new_end, 3)
        candidate.boundary_method = "cues"
        start_score, start_reasons = _cue_start_score(cues, first)
        end_score, end_reasons = _cue_end_score(cues, last)
        candidate.boundary_score = round((start_score + end_score) / 2.0, 1)
        candidate.boundary_reasons = [
            *(f"start:{reason}" for reason in start_reasons),
            *(f"end:{reason}" for reason in end_reasons),
        ]
        _mark_boundary_result(candidate, original_start, original_end, min_duration, max_duration)
        refined.append(candidate)

    return refined




def _cue_is_complete_end(cues: list[SubtitleCue], index: int) -> bool:
    if _is_sentence_end(cues[index].text):
        return True
    if index + 1 >= len(cues):
        return True
    gap = max(0.0, cues[index + 1].start - cues[index].end)
    return gap >= 0.6

def _cue_start_score(cues: list[SubtitleCue], index: int) -> tuple[float, list[str]]:
    if index == 0:
        return 85.0, ["transcript_start", "cue_boundary"]
    gap = max(0.0, cues[index].start - cues[index - 1].end)
    score = 35.0 + _pause_score(gap)
    reasons = ["cue_boundary"]
    if gap >= 0.3:
        reasons.append(f"pause_{gap:.2f}s")
    if _is_sentence_end(cues[index - 1].text):
        score += 20.0
        reasons.append("previous_sentence_end")
    return min(100.0, score), reasons


def _cue_end_score(cues: list[SubtitleCue], index: int) -> tuple[float, list[str]]:
    score = 35.0
    reasons = ["cue_boundary"]
    if _is_sentence_end(cues[index].text):
        score += 30.0
        reasons.append("sentence_end")
    if index + 1 >= len(cues):
        score += 35.0
        reasons.append("transcript_end")
    else:
        gap = max(0.0, cues[index + 1].start - cues[index].end)
        score += _pause_score(gap)
        if gap >= 0.3:
            reasons.append(f"pause_{gap:.2f}s")
    return min(100.0, score), reasons


def _overlapping_cue_indexes(cues: list[SubtitleCue], start: float, end: float) -> tuple[int, int] | None:
    indexes = [index for index, cue in enumerate(cues) if cue.end > start and cue.start < end]
    if indexes:
        return indexes[0], indexes[-1]
    if not cues:
        return None
    midpoint = (start + end) / 2.0
    nearest = min(
        range(len(cues)),
        key=lambda index: abs(((cues[index].start + cues[index].end) / 2.0) - midpoint),
    )
    return nearest, nearest


def _mark_boundary_result(
    candidate: ReelCandidate,
    original_start: float,
    original_end: float,
    min_duration: int,
    max_duration: int,
) -> None:
    candidate.warnings = [
        warning
        for warning in candidate.warnings
        if warning not in {"too_short", "too_long", "boundary_low_confidence"}
    ]
    changed = abs(candidate.start - original_start) > 0.05 or abs(candidate.end - original_end) > 0.05
    if changed and "boundary_refined" not in candidate.warnings:
        candidate.warnings.append("boundary_refined")
    if candidate.duration < min_duration:
        candidate.warnings.append("too_short")
    if candidate.duration > max_duration:
        candidate.warnings.append("too_long")
    if candidate.boundary_score is not None and candidate.boundary_score < 45.0:
        candidate.warnings.append("boundary_low_confidence")
    end_reasons = [reason for reason in candidate.boundary_reasons if reason.startswith("end:")]
    if end_reasons and not any(
        token in reason
        for reason in end_reasons
        for token in ("sentence_end", "pause_0.6", "pause_0.7", "pause_0.8", "pause_0.9", "pause_1", "transcript_end", "speaker_change")
    ):
        candidate.warnings.append("boundary_incomplete_end")


def _is_sentence_end(text: str) -> bool:
    return text.strip().endswith(_SENTENCE_ENDINGS)


def _remove_near_duplicates(candidates: list[ReelCandidate]) -> list[ReelCandidate]:
    unique: list[ReelCandidate] = []
    seen: set[tuple[object, str]] = set()
    for candidate in candidates:
        segment_key = tuple((round(segment.start), round(segment.end)) for segment in candidate.source_segments)
        key = (segment_key, candidate.title.lower().strip()[:30])
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique
