from pathlib import Path

from reelmaker.analyzer import generate_candidates, local_rank_candidates
from reelmaker.models import ReelCandidate, TranscriptChunk


class FailingClient:
    def generate(self, prompt: str) -> str:
        raise AssertionError("Ollama should not be called when raw log cache is reusable")


def test_generate_candidates_reuses_existing_raw_log(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "ollama_chunk_001.txt").write_text(
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
    assert (logs_dir / "ollama_chunk_001.candidates.json").exists()


def test_local_rank_penalizes_warnings():
    good = ReelCandidate("C001", 0, 30, "A", "hook", "reason", 7.5, "txt")
    warned = ReelCandidate("C002", 0, 30, "B", "hook", "reason", 9.0, "txt", warnings=["outside_source_chunk"])

    ranked = local_rank_candidates([warned, good], shortlist_count=2)

    assert ranked[0] == good
