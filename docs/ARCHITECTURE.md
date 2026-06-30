# Architecture

## Current pipeline

```text
subtitle file or YouTube
  -> SubtitleCue list
  -> transcript chunks
  -> Ollama candidate generation
  -> local/optional Ollama ranking
  -> human selection
  -> subtitle correction + crop hint
  -> FFmpeg render
```

## Current module responsibilities

- `cli.py`: command-line orchestration and dependency wiring.
- `models.py`: shared dataclasses.
- `subtitles.py`: subtitle parsing, chunking, and segment normalization.
- `youtube.py`: yt-dlp adapter.
- `ollama_client.py`: Ollama HTTP adapter and JSON extraction.
- `analyzer.py`: candidate generation, boundary refinement, ranking, selection.
- `vision.py`: lightweight crop hints.
- `renderer.py`: ASS/caption generation and FFmpeg rendering.

## Target boundary for direct MP4 input

Do not add WhisperX calls directly to `cli.py` or `subtitles.py`.

```text
TranscriptionProvider
  transcribe(request) -> TranscriptResult

providers:
  ExistingSubtitleProvider
  YouTubeSubtitleProvider
  WhisperXProvider
```

`TranscriptResult` should contain normalized cues, optional words, language, provider metadata, and a cache signature. Downstream analysis should consume this result without knowing which provider produced it.

## Output compatibility

JSON is the interchange format between expensive stages. New schemas should include a `schema_version`. Cache reuse must depend on both input fingerprint and processing settings.

## Deliberate non-goals

- no database until local JSON becomes demonstrably insufficient;
- no web framework before the CLI pipeline is stable;
- no plugin framework for only two providers;
- no large model abstraction layer beyond the concrete need.
