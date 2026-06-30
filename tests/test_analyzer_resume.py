from pathlib import Path

from reelmaker.analyzer import generate_candidates, local_rank_candidates
from reelmaker.models import ReelCandidate, TranscriptChunk


class FailingClient:
    def generate(self, prompt: str, *, json_schema=None) -> str:
        raise AssertionError("Ollama should not be called when raw log cache is reusable")


def test_generate_candidates_reuses_existing_raw_log(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "ollama_chunk_001.impact_v2.txt").write_text(
        '{"candidates":[{"start_time":"00:00:10,000","end_time":"00:00:40,000",'
        '"title":"Titre","hook":"Hook","reason":"Raison","score":8,'
        '"transcript_excerpt":"Texte"}]}',
        encoding="utf-8",
    )
    chunk = TranscriptChunk(index=1, start=0, end=60, text="dummy", cue_indexes=[1])

    candidates = generate_candidates(
        [chunk],
        FailingClient(),  # type: ignore[arg-type]
        logs_dir,
        candidates_per_chunk=3,
        min_duration=15,
        max_duration=75,
        resume=True,
    )

    assert len(candidates) == 1
    assert candidates[0].id == "C001"
    assert candidates[0].start == 10
    assert candidates[0].end == 40
    assert (logs_dir / "ollama_chunk_001.impact_v2.candidates.json").exists()


def test_local_rank_penalizes_warnings():
    good = ReelCandidate("C001", 0, 30, "A", "hook", "reason", 7.5, "txt")
    warned = ReelCandidate("C002", 0, 30, "B", "hook", "reason", 9.0, "txt", warnings=["outside_source_chunk"])

    ranked = local_rank_candidates([warned, good], shortlist_count=2)

    assert ranked[0] == good

from reelmaker.boundary import refine_candidate_boundaries
from reelmaker.models import SubtitleCue


def test_refine_candidate_boundaries_expands_short_candidate():
    candidate = ReelCandidate("C001", 10, 14, "A", "hook", "reason", 8.0, "txt", warnings=["too_short"])
    cues = [
        SubtitleCue(1, 10, 14, "La maman couve."),
        SubtitleCue(2, 14.2, 18, "Pendant trente jours."),
        SubtitleCue(3, 18.2, 23, "Les petits restent dans le nichoir."),
        SubtitleCue(4, 23.2, 28, "Ensuite ils apprennent a voler."),
    ]

    refined = refine_candidate_boundaries([candidate], cues, min_duration=18, target_duration=22, max_duration=60)

    assert len(refined) == 1
    assert refined[0].duration >= 18
    assert "too_short" not in refined[0].warnings
    assert "boundary_refined" in refined[0].warnings


def test_generate_candidates_renumbers_mixed_cached_chunks(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    for chunk_index, start in [(1, 10), (2, 70)]:
        (logs_dir / f"ollama_chunk_{chunk_index:03d}.impact_v2.candidates.json").write_text(
            '[{"id":"C001","start":%s,"end":%s,"title":"Titre","hook":"Hook",'
            '"reason":"Raison","score":8,"transcript_excerpt":"Texte","warnings":[]}]'
            % (start, start + 30),
            encoding="utf-8",
        )

    chunks = [
        TranscriptChunk(index=1, start=0, end=60, text="one", cue_indexes=[1]),
        TranscriptChunk(index=2, start=60, end=120, text="two", cue_indexes=[2]),
    ]

    candidates = generate_candidates(chunks, FailingClient(), logs_dir, resume=True)  # type: ignore[arg-type]

    assert [candidate.id for candidate in candidates] == ["C001", "C002"]
