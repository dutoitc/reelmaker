from pathlib import Path

from reelmaker.analyzer import generate_candidates
from reelmaker.models import ReelSegment, ReelSelection, SubtitleCue, TranscriptChunk
from reelmaker.progress import TimingHistory
from reelmaker.subtitles import cues_for_segments, split_cues_for_display


class CompositeClient:
    def generate(self, prompt: str, *, json_schema=None) -> str:
        return """{
          "candidates": [{
            "start_time": "00:00:10,000",
            "end_time": "00:01:20,000",
            "title": "Montage",
            "hook": "Pourquoi cette plante change le sol ?",
            "reason": "Deux explications complementaires",
            "score": 9,
            "transcript_excerpt": "Extrait compose",
            "segments": [
              {"start_time": "00:00:10,000", "end_time": "00:00:20,000"},
              {"start_time": "00:01:00,000", "end_time": "00:01:15,000"}
            ]
          }]
        }"""


def test_hybrid_candidate_keeps_multiple_source_segments(tmp_path: Path):
    chunk = TranscriptChunk(index=1, start=0, end=120, text="dummy", cue_indexes=[1])

    candidates = generate_candidates(
        [chunk],
        CompositeClient(),  # type: ignore[arg-type]
        tmp_path,
        min_duration=10,
        max_duration=60,
        composition_mode="hybrid",
        resume=False,
    )

    assert len(candidates) == 1
    assert candidates[0].is_composite
    assert [(segment.start, segment.end) for segment in candidates[0].source_segments] == [
        (10.0, 20.0),
        (60.0, 75.0),
    ]
    assert candidates[0].duration == 25.0


def test_reel_selection_duration_is_sum_of_segments():
    candidate = ReelSelection(
        "R01",
        "C001",
        1,
        10.0,
        75.0,
        "Titre",
        "Hook",
        "Raison",
        "",
        segments=[ReelSegment(10.0, 20.0), ReelSegment(60.0, 75.0)],
    )
    assert candidate.duration == 25.0


def test_cues_for_segments_builds_continuous_timeline():
    cues = [
        SubtitleCue(1, 10.0, 12.0, "Premier"),
        SubtitleCue(2, 30.0, 33.0, "Deuxieme"),
    ]

    result = cues_for_segments(cues, [(10.0, 15.0), (30.0, 35.0)])

    assert [(cue.start, cue.end, cue.text) for cue in result] == [
        (0.0, 2.0, "Premier"),
        (5.0, 8.0, "Deuxieme"),
    ]


def test_split_long_cue_preserves_complete_text():
    original = "La luzerne fixe naturellement l azote et contribue a ameliorer durablement la structure du sol agricole"
    result = split_cues_for_display(
        [SubtitleCue(1, 0.0, 8.0, original)],
        max_chars=32,
    )

    assert len(result) >= 2
    assert " ".join(cue.text for cue in result) == original
    assert result[0].start == 0.0
    assert result[-1].end == 8.0


def test_timing_history_uses_previous_runs(tmp_path: Path):
    history = TimingHistory(tmp_path / "timings.json")
    history.record("whisper:gpu", elapsed_seconds=120.0, units=600.0)
    history.record("whisper:gpu", elapsed_seconds=100.0, units=500.0)

    estimate = history.estimate_seconds("whisper:gpu", 300.0)

    assert estimate == 60.0
    assert (tmp_path / "timings.json").exists()
