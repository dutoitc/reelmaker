from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Protocol

from .models import (
    TRANSCRIPT_SCHEMA_VERSION,
    SubtitleCue,
    TranscriptDocument,
    TranscriptionResult,
    TranscriptWord,
)
from .subtitles import clean_subtitle_text, load_subtitles
from .transcript_io import (
    fingerprint_file,
    fingerprint_settings,
    fingerprint_text,
    read_transcript_document,
    write_transcript_outputs,
)
from .youtube import copy_local_subtitle, extract_youtube_subtitles


class TranscriptionProvider(Protocol):
    name: str

    @property
    def source(self) -> str: ...

    def source_fingerprint(self) -> str: ...

    def settings(self) -> dict[str, Any]: ...

    def transcribe(self) -> TranscriptionResult: ...


@dataclass(frozen=True)
class WhisperXConfig:
    model: str = "large-v3"
    language: str = "fr"
    device: str = "auto"
    compute_type: str = "auto"
    batch_size: int = 4


class LocalSubtitleProvider:
    name = "subtitle_file"

    def __init__(self, subtitle_path: Path, subtitles_dir: Path) -> None:
        self.subtitle_path = subtitle_path
        self.subtitles_dir = subtitles_dir

    @property
    def source(self) -> str:
        return str(self.subtitle_path.resolve())

    def source_fingerprint(self) -> str:
        return fingerprint_file(self.subtitle_path)

    def settings(self) -> dict[str, Any]:
        return {"format": self.subtitle_path.suffix.lower().lstrip(".") or "srt"}

    def transcribe(self) -> TranscriptionResult:
        copied_path = copy_local_subtitle(self.subtitle_path, self.subtitles_dir)
        cues = load_subtitles(copied_path)
        return TranscriptionResult(language="unknown", cues=cues)


class YouTubeSubtitleProvider:
    name = "youtube_subtitles"

    def __init__(self, youtube_url: str, subtitles_dir: Path, subtitle_langs: str) -> None:
        self.youtube_url = youtube_url
        self.subtitles_dir = subtitles_dir
        self.subtitle_langs = subtitle_langs

    @property
    def source(self) -> str:
        return self.youtube_url

    def source_fingerprint(self) -> str:
        return fingerprint_text(self.youtube_url)

    def settings(self) -> dict[str, Any]:
        return {"subtitle_langs": self.subtitle_langs}

    def transcribe(self) -> TranscriptionResult:
        subtitle_path = extract_youtube_subtitles(
            self.youtube_url,
            self.subtitles_dir,
            subtitle_langs=self.subtitle_langs,
        )
        cues = load_subtitles(subtitle_path)
        return TranscriptionResult(language="unknown", cues=cues)


class WhisperXProvider:
    name = "whisperx"

    def __init__(
        self,
        video_path: Path,
        config: WhisperXConfig,
        *,
        module_loader: Callable[[str], Any] = importlib.import_module,
    ) -> None:
        self.video_path = video_path
        self.config = config
        self._module_loader = module_loader

    @property
    def source(self) -> str:
        return str(self.video_path.resolve())

    def source_fingerprint(self) -> str:
        return fingerprint_file(self.video_path)

    def settings(self) -> dict[str, Any]:
        try:
            whisperx_version = metadata.version("whisperx")
        except metadata.PackageNotFoundError:
            whisperx_version = "not-installed"
        return {**asdict(self.config), "whisperx_version": whisperx_version}

    def transcribe(self) -> TranscriptionResult:
        try:
            whisperx = self._module_loader("whisperx")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                'WhisperX is not installed. Activate the Python 3.11 environment and run: '
                'pip install -e ".[transcription]"'
            ) from exc

        device = self._resolve_device()
        compute_type = self._resolve_compute_type(device)
        language = None if self.config.language.lower() == "auto" else self.config.language

        audio = whisperx.load_audio(str(self.video_path))
        model = whisperx.load_model(
            self.config.model,
            device,
            compute_type=compute_type,
            language=language,
        )
        raw_result = model.transcribe(audio, batch_size=self.config.batch_size)
        detected_language = str(raw_result.get("language") or language or "unknown")
        raw_segments = raw_result.get("segments") or []
        if not raw_segments:
            raise RuntimeError("WhisperX returned no speech segments")

        align_model, align_metadata = whisperx.load_align_model(
            language_code=detected_language,
            device=device,
        )
        aligned = whisperx.align(
            raw_segments,
            align_model,
            align_metadata,
            audio,
            device,
            return_char_alignments=False,
        )
        return _result_from_whisperx(aligned, detected_language)

    def _resolve_device(self) -> str:
        if self.config.device != "auto":
            return self.config.device
        try:
            torch = self._module_loader("torch")
        except ModuleNotFoundError:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _resolve_compute_type(self, device: str) -> str:
        if self.config.compute_type != "auto":
            return self.config.compute_type
        return "float16" if device == "cuda" else "int8"


def load_or_transcribe(
    provider: TranscriptionProvider,
    output_dir: Path,
    *,
    force: bool = False,
) -> tuple[TranscriptDocument, bool]:
    cache_path = output_dir / "transcript.json"
    source_fingerprint = provider.source_fingerprint()
    settings = provider.settings()
    settings_fingerprint = fingerprint_settings(settings)

    if not force and cache_path.exists():
        try:
            cached = read_transcript_document(cache_path)
        except (OSError, ValueError, KeyError, TypeError):
            cached = None
        if (
            cached is not None
            and cached.provider == provider.name
            and cached.source_fingerprint == source_fingerprint
            and cached.settings_fingerprint == settings_fingerprint
            and cached.cues
        ):
            write_transcript_outputs(output_dir, cached)
            return cached, True

    result = provider.transcribe()
    if not result.cues:
        raise RuntimeError(f"No subtitle cues produced by {provider.name}")

    document = TranscriptDocument(
        schema_version=TRANSCRIPT_SCHEMA_VERSION,
        provider=provider.name,
        language=result.language,
        source=provider.source,
        source_fingerprint=source_fingerprint,
        settings=settings,
        settings_fingerprint=settings_fingerprint,
        cues=result.cues,
        words=result.words,
    )
    write_transcript_outputs(output_dir, document)
    return document, False


def _result_from_whisperx(data: Any, language: str) -> TranscriptionResult:
    if not isinstance(data, dict):
        raise RuntimeError("WhisperX alignment result must be an object")
    segments = data.get("segments")
    if not isinstance(segments, list):
        raise RuntimeError("WhisperX alignment result has no segment list")

    cues: list[SubtitleCue] = []
    words: list[TranscriptWord] = []
    word_index = 1

    for raw_segment in segments:
        if not isinstance(raw_segment, dict):
            continue
        raw_words = raw_segment.get("words")
        segment_words = raw_words if isinstance(raw_words, list) else []
        timed_words = [
            word
            for word in segment_words
            if isinstance(word, dict) and _valid_interval(word.get("start"), word.get("end"))
        ]

        start = _optional_float(raw_segment.get("start"))
        end = _optional_float(raw_segment.get("end"))
        if (start is None or end is None or end <= start) and timed_words:
            start = float(timed_words[0]["start"])
            end = float(timed_words[-1]["end"])
        if start is None or end is None or end <= start:
            continue

        text = clean_subtitle_text(str(raw_segment.get("text") or ""))
        if not text and segment_words:
            text = clean_subtitle_text(" ".join(str(word.get("word") or "") for word in segment_words))
        if not text:
            continue

        cue_index = len(cues) + 1
        cues.append(SubtitleCue(index=cue_index, start=start, end=end, text=text))

        segment_speaker = _optional_text(raw_segment.get("speaker"))
        for raw_word in timed_words:
            word_text = clean_subtitle_text(str(raw_word.get("word") or raw_word.get("text") or ""))
            if not word_text:
                continue
            words.append(
                TranscriptWord(
                    index=word_index,
                    cue_index=cue_index,
                    start=float(raw_word["start"]),
                    end=float(raw_word["end"]),
                    text=word_text,
                    score=_optional_float(raw_word.get("score")),
                    speaker=_optional_text(raw_word.get("speaker")) or segment_speaker,
                )
            )
            word_index += 1

    if not cues:
        raise RuntimeError("WhisperX alignment produced no usable timed segments")
    return TranscriptionResult(language=language, cues=cues, words=words)


def _valid_interval(start: Any, end: Any) -> bool:
    start_value = _optional_float(start)
    end_value = _optional_float(end)
    return start_value is not None and end_value is not None and end_value > start_value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
