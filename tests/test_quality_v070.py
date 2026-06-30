from __future__ import annotations

from pathlib import Path

from reelmaker.analyzer import generate_global_composite_candidates
from reelmaker.boundary import refine_candidate_boundaries
from reelmaker.cli import build_parser
from reelmaker.models import ReelCandidate, SubtitleCue
from reelmaker.renderer import write_ass_subtitles
from reelmaker.subtitle_corrector import correct_text_basic
from reelmaker.subtitles import split_cues_for_display
from reelmaker.visual_text import score_text_bands


class CompositeClient:
    model = "test"

    def generate(self, prompt: str, *, json_schema=None) -> str:
        return (
            '{"candidates":[{"start_time":"00:00:00,000","end_time":"00:00:30,000",'
            '"segments":[{"start_time":"00:00:00,000","end_time":"00:00:10,000"},'
            '{"start_time":"00:00:20,000","end_time":"00:00:30,000"}],'
            '"title":"Angle fort","hook":"Pourquoi cela change tout",'
            '"reason":"Accroche puis consequence","score":9,'
            '"transcript_excerpt":"Texte"}]}'
        )


def test_ass_subtitle_never_truncates_text(tmp_path: Path):
    path = tmp_path / "subtitles.ass"
    text = "Cette phrase contient beaucoup de mots et doit rester entièrement visible sans points de suspension artificiels."
    write_ass_subtitles(path, [SubtitleCue(1, 0, 4, text)], wrap_width=18, max_lines=2)
    raw = path.read_text(encoding="utf-8")
    assert "..." not in raw
    for word in text.rstrip(".").split():
        assert word in raw


def test_long_caption_is_split_without_losing_words():
    text = "un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze"
    cues = split_cues_for_display([SubtitleCue(1, 0.0, 1.0, text)], max_chars=20)
    assert len(cues) > 1
    assert " ".join(cue.text for cue in cues) == text
    assert cues[0].start == 0.0
    assert cues[-1].end == 1.0


def test_nord_vaudois_dictionary_and_accents():
    corrected = correct_text_basic("on part de val orbe pour les clees puis romainmotier et chavornay")
    assert corrected == "On part de Vallorbe pour Les Clées puis Romainmôtier et Chavornay"


def test_boundary_can_extend_two_seconds_to_finish_sentence():
    candidate = ReelCandidate("C001", 0.0, 9.8, "Titre", "Hook", "Raison", 8.0, "Texte")
    cues = [
        SubtitleCue(1, 0.0, 9.8, "La phrase commence mais"),
        SubtitleCue(2, 10.0, 11.5, "elle se termine ici."),
    ]
    refined = refine_candidate_boundaries(
        [candidate],
        cues,
        mode="cues",
        min_duration=5,
        target_duration=10,
        max_duration=10,
        max_end_extension=2.0,
        post_padding=0.0,
    )[0]
    assert refined.end == 11.5
    assert "extended_for_complete_sentence" in refined.warnings
    assert "boundary_incomplete_end" not in refined.warnings


def test_global_composite_candidates_are_added(tmp_path: Path):
    cues = [
        SubtitleCue(1, 0.0, 10.0, "Premier fait concret."),
        SubtitleCue(2, 20.0, 30.0, "Sa consequence est importante."),
    ]
    candidates = generate_global_composite_candidates(
        cues,
        CompositeClient(),  # type: ignore[arg-type]
        tmp_path,
        max_candidates=2,
        resume=False,
    )
    assert len(candidates) == 1
    assert candidates[0].is_composite
    assert "global_composite" in candidates[0].warnings


def test_quality_defaults():
    args = build_parser().parse_args(["all", "--source-video", "video.mp4"])
    assert args.candidates_per_chunk == 5
    assert args.global_composite_count == 3
    assert args.ranking_mode == "ollama"
    assert args.subtitle_position == "auto"
    assert args.end_card_seconds == 1.5
    assert args.youtube_cta == "Voir sur YouTube"


def test_visual_text_detector_finds_bottom_title():
    try:
        import cv2
        import numpy as np
    except ImportError:
        return
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(frame, "TEXTE EXISTANT", (120, 650), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 255, 255), 5)
    scores = score_text_bands([frame], cv2=cv2)
    assert scores.has_text
    assert scores.preferred_subtitle_position == "top"


def test_single_long_word_is_preserved_and_font_reduced(tmp_path: Path):
    path = tmp_path / "long_word.ass"
    word = "anticonstitutionnellementextraordinaire"
    write_ass_subtitles(path, [SubtitleCue(1, 0, 2, word)], wrap_width=12, max_lines=2)
    raw = path.read_text(encoding="utf-8")
    assert word in raw
    assert "\\fs" in raw


def test_smart_mode_keeps_fit_blur_face_hint(monkeypatch, tmp_path: Path):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return
    from reelmaker import vision
    from reelmaker.vision import CropHint

    video = tmp_path / "video.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 180))
    for _ in range(10):
        writer.write(np.zeros((180, 320, 3), dtype=np.uint8))
    writer.release()

    monkeypatch.setattr(
        vision,
        "_detect_face_hint_from_frames",
        lambda *args, **kwargs: CropHint(None, "two_person_shot_preserved", 0.9, "fit-blur"),
    )
    hint = vision.detect_smart_crop_hint(source_video=video, start=0, duration=1, mode="smart")
    assert hint.layout == "fit-blur"
    assert hint.reason == "two_person_shot_preserved"
