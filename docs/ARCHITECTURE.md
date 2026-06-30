# Architecture

## Pipeline

```text
MP4 / SRT / YouTube
  -> TranscriptionProvider
  -> TranscriptDocument schema v1
  -> transcript chunks
  -> Ollama candidate generation
  -> boundary refinement and ranking
  -> human selection
  -> subtitle correction + crop hint
  -> FFmpeg render
```

## Module responsibilities

- `cli.py`: command orchestration and dependency wiring only.
- `models.py`: shared typed dataclasses and transcript schema version.
- `transcription.py`: provider protocol and SRT, YouTube, WhisperX adapters.
- `transcript_io.py`: JSON/SRT persistence and cache fingerprints.
- `subtitles.py`: parsing, chunking and reel subtitle normalization.
- `youtube.py`: yt-dlp adapter.
- `ollama_client.py`: Ollama HTTP adapter and JSON extraction.
- `analyzer.py`: candidate generation, ranking and human selection.
- `boundary.py`: pause/cue boundary scoring and cut snapping.
- `vision.py`: lightweight crop hints.
- `renderer.py`: ASS/caption generation and FFmpeg rendering.

## Transcription boundary

```text
TranscriptionProvider
  source
  source_fingerprint()
  settings()
  transcribe() -> TranscriptionResult

providers:
  LocalSubtitleProvider
  YouTubeSubtitleProvider
  WhisperXProvider
```

Downstream code consumes `TranscriptDocument` and does not know which provider produced it.

WhisperX is imported lazily inside `WhisperXProvider.transcribe()`. Base CLI startup and SRT/YouTube use do not load Torch or WhisperX.

## Transcript schema v1

`transcript.json` contains:

- provider and language;
- source identity and source fingerprint;
- settings and settings fingerprint;
- normalized subtitle cues;
- aligned words with cue link, start/end, confidence and optional speaker.

The cache is valid only when provider, source fingerprint and settings fingerprint match.

## Boundary analysis

`boundary.py` consumes only normalized `SubtitleCue` and `TranscriptWord` objects.

Word mode builds possible boundaries at word starts and ends, then scores:

- actual silence before/after the word;
- sentence punctuation;
- subtitle cue transition;
- optional speaker transition;
- distance from the candidate proposed by Ollama.

Pre/post padding is clamped to available silence. It must never extend into the next spoken word.

Cue mode provides backward compatibility for SRT/VTT sources. Boundary metadata is optional, so older candidate cache files remain readable.

## Anti-spaghetti constraints

- do not put transcription implementation in `cli.py`;
- do not make `analyzer.py` depend directly on WhisperX structures;
- keep boundary/prosody analysis outside `analyzer.py`;
- add pitch as a separate signal in `boundary.py` or a dedicated prosody module only after measurement;
- add scene analysis outside `renderer.py`, then pass explicit scene decisions;
- keep provider failures explicit; no silent cloud fallback;
- add a schema version before changing persisted transcript structure.

## Deliberate non-goals

- no diarization workflow exposed yet;
- no pitch/prosody scoring yet;
- no scene ranking or B-roll yet;
- no database or web framework while the CLI pipeline is evolving.
