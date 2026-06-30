from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from reelmaker.cli import build_parser, choose_transcription_mode
from reelmaker.models import SubtitleCue, TranscriptionResult, TranscriptWord
from reelmaker.transcription import WhisperXConfig, WhisperXProvider, load_or_transcribe


class FakeProvider:
    name = "fake"

    def __init__(self, source_path: Path, *, revision: int = 1) -> None:
        self.source_path = source_path
        self.revision = revision
        self.calls = 0

    @property
    def source(self) -> str:
        return str(self.source_path.resolve())

    def source_fingerprint(self) -> str:
        return f"source:{self.source_path.read_text(encoding='utf-8')}"

    def settings(self) -> dict[str, Any]:
        return {"revision": self.revision}

    def transcribe(self) -> TranscriptionResult:
        self.calls += 1
        return TranscriptionResult(
            language="fr",
            cues=[SubtitleCue(1, 0.0, 1.5, "Bonjour Orbe")],
            words=[TranscriptWord(1, 1, 0.0, 0.6, "Bonjour", 0.95)],
        )


def test_transcription_cache_reuses_same_source_and_settings(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_text("video-content", encoding="utf-8")
    output = tmp_path / "output"
    provider = FakeProvider(source)

    first, first_reused = load_or_transcribe(provider, output)
    second, second_reused = load_or_transcribe(provider, output)

    assert first_reused is False
    assert second_reused is True
    assert provider.calls == 1
    assert second.words[0].text == "Bonjour"
    assert (output / "transcript.json").exists()
    assert (output / "transcript.srt").exists()
    assert first.settings_fingerprint == second.settings_fingerprint


def test_transcription_cache_invalidates_when_settings_change(tmp_path: Path):
    source = tmp_path / "video.mp4"
    source.write_text("video-content", encoding="utf-8")
    output = tmp_path / "output"

    first_provider = FakeProvider(source, revision=1)
    second_provider = FakeProvider(source, revision=2)
    load_or_transcribe(first_provider, output)
    _, reused = load_or_transcribe(second_provider, output)

    assert reused is False
    assert first_provider.calls == 1
    assert second_provider.calls == 1


def test_auto_transcription_mode_preserves_existing_workflow():
    parser = build_parser()

    source_only = parser.parse_args(["transcribe", "--source-video", "video.mp4"])
    subtitle = parser.parse_args(["transcribe", "--subtitle-file", "video.srt"])
    youtube = parser.parse_args(["transcribe", "--youtube-url", "https://youtu.be/example"])

    assert choose_transcription_mode(source_only) == "whisperx"
    assert choose_transcription_mode(subtitle) == "subtitles"
    assert choose_transcription_mode(youtube) == "subtitles"


def test_transcription_module_does_not_import_whisperx_at_startup():
    assert "whisperx" not in sys.modules


def test_whisperx_provider_preserves_aligned_word_timestamps(tmp_path: Path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake-video")

    class FakeModel:
        def transcribe(self, audio: object, batch_size: int) -> dict[str, Any]:
            assert batch_size == 4
            return {
                "language": "fr",
                "segments": [{"start": 1.0, "end": 3.0, "text": "Bonjour Orbe"}],
            }

    fake_whisperx = SimpleNamespace(
        load_audio=lambda path: f"audio:{path}",
        load_model=lambda model, device, compute_type, language: FakeModel(),
        load_align_model=lambda language_code, device: ("align-model", {"language": language_code}),
        align=lambda segments, model, metadata, audio, device, return_char_alignments: {
            "segments": [
                {
                    "start": 1.0,
                    "end": 3.0,
                    "text": " Bonjour Orbe ",
                    "words": [
                        {"word": " Bonjour", "start": 1.0, "end": 1.7, "score": 0.98},
                        {"word": " Orbe", "start": 1.8, "end": 2.4, "score": 0.96},
                    ],
                }
            ]
        },
    )
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True))

    def load_module(name: str) -> Any:
        if name == "whisperx":
            return fake_whisperx
        if name == "torch":
            return fake_torch
        raise ModuleNotFoundError(name)

    provider = WhisperXProvider(
        video,
        WhisperXConfig(model="large-v3", language="fr", batch_size=4),
        module_loader=load_module,
    )
    result = provider.transcribe()

    assert result.language == "fr"
    assert result.cues == [SubtitleCue(1, 1.0, 3.0, "Bonjour Orbe")]
    assert [(word.text, word.start, word.end) for word in result.words] == [
        ("Bonjour", 1.0, 1.7),
        ("Orbe", 1.8, 2.4),
    ]
