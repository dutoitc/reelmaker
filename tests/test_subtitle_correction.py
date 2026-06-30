from reelmaker.subtitle_corrector import correct_text_basic, correct_cues_basic
from reelmaker.models import SubtitleCue


def test_basic_subtitle_correction_spacing_and_case():
    assert correct_text_basic(" les eclosons  ne sont pas tout au meme temps ! ") == "Les eclosions ne sont pas tout au meme temps!"


def test_basic_cue_correction_keeps_timing():
    cues = [SubtitleCue(1, 1.0, 2.0, " chouette hulote , ok ")]
    corrected = correct_cues_basic(cues)
    assert corrected[0].start == 1.0
    assert corrected[0].end == 2.0
    assert corrected[0].text == "Chouette hulotte, ok"


def test_ollama_partial_response_keeps_basic_correction_for_missing_items(tmp_path):
    from reelmaker.models import ReelSelection
    from reelmaker.subtitle_corrector import correct_cues_with_ollama

    class PartialClient:
        def generate(self, prompt: str) -> str:
            return '{"subtitles":[{"index":1,"text":"premier corrige"}]}'

    cues = [
        SubtitleCue(1, 0.0, 1.0, " premier "),
        SubtitleCue(2, 1.0, 2.0, " hulote "),
    ]
    selection = ReelSelection("R01", "C001", 1, 0.0, 2.0, "Titre", "Hook", "Raison", "")

    corrected = correct_cues_with_ollama(
        cues,
        selection=selection,
        episode_title="",
        client=PartialClient(),  # type: ignore[arg-type]
        cache_path=tmp_path / "corrected.json",
    )

    assert [cue.text for cue in corrected] == ["Premier corrige", "Hulotte"]
