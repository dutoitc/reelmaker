from reelmaker.boundary import refine_candidate_boundaries
from reelmaker.models import ReelCandidate, SubtitleCue, TranscriptWord


def _candidate(start: float, end: float) -> ReelCandidate:
    return ReelCandidate("C001", start, end, "Titre", "Hook", "Raison", 8.0, "Extrait")


def test_word_boundaries_prefer_pause_and_sentence_end():
    candidate = _candidate(5.2, 6.8)
    cues = [
        SubtitleCue(1, 0.0, 4.0, "Une introduction."),
        SubtitleCue(2, 4.8, 9.0, "Voici le fait essentiel."),
        SubtitleCue(3, 10.2, 14.0, "Puis une autre idée."),
    ]
    words = [
        TranscriptWord(1, 1, 0.0, 0.4, "Une"),
        TranscriptWord(2, 1, 0.5, 1.3, "introduction."),
        TranscriptWord(3, 2, 4.8, 5.2, "Voici"),
        TranscriptWord(4, 2, 5.3, 5.7, "le"),
        TranscriptWord(5, 2, 5.8, 6.2, "fait"),
        TranscriptWord(6, 2, 6.3, 7.0, "essentiel."),
        TranscriptWord(7, 3, 10.2, 10.7, "Puis"),
        TranscriptWord(8, 3, 10.8, 11.2, "une"),
        TranscriptWord(9, 3, 11.3, 11.8, "autre"),
        TranscriptWord(10, 3, 11.9, 12.5, "idée."),
    ]

    result = refine_candidate_boundaries(
        [candidate],
        cues,
        words,
        min_duration=2,
        target_duration=4,
        max_duration=20,
        pre_padding=0.2,
        post_padding=0.4,
    )[0]

    assert result.start == 4.6
    assert result.end == 7.4
    assert result.boundary_method == "words"
    assert result.boundary_score is not None and result.boundary_score >= 60
    assert any(reason.startswith("start:previous_sentence_end") for reason in result.boundary_reasons)
    assert any(reason.startswith("end:pause_") for reason in result.boundary_reasons)


def test_auto_falls_back_to_cues_without_word_timestamps():
    candidate = _candidate(10.0, 14.0)
    cues = [
        SubtitleCue(1, 10.0, 14.0, "La maman couve."),
        SubtitleCue(2, 14.5, 19.0, "Pendant trente jours."),
        SubtitleCue(3, 19.5, 24.0, "Les petits grandissent."),
    ]

    result = refine_candidate_boundaries(
        [candidate],
        cues,
        [],
        min_duration=10,
        target_duration=12,
        max_duration=30,
    )[0]

    assert result.boundary_method == "cues"
    assert result.duration >= 10
    assert result.boundary_score is not None


def test_boundary_mode_off_preserves_candidate():
    candidate = _candidate(10.0, 14.0)
    cues = [SubtitleCue(1, 10.0, 14.0, "Texte.")]

    result = refine_candidate_boundaries([candidate], cues, mode="off")[0]

    assert result.start == 10.0
    assert result.end == 14.0
    assert result.boundary_method is None


def test_word_padding_never_overlaps_next_spoken_word():
    candidate = _candidate(0.0, 2.0)
    cues = [
        SubtitleCue(1, 0.0, 2.0, "Première phrase."),
        SubtitleCue(2, 2.2, 4.0, "Phrase suivante."),
    ]
    words = [
        TranscriptWord(1, 1, 0.0, 0.8, "Première"),
        TranscriptWord(2, 1, 0.9, 2.0, "phrase."),
        TranscriptWord(3, 2, 2.2, 2.8, "Phrase"),
        TranscriptWord(4, 2, 2.9, 4.0, "suivante."),
    ]

    result = refine_candidate_boundaries(
        [candidate],
        cues,
        words,
        min_duration=1,
        target_duration=2,
        max_duration=10,
        post_padding=1.2,
    )[0]

    assert result.end == 2.2
