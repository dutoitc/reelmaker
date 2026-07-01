# Project manifest — Reelmaker

## Snapshot

- Version: **0.8.1**
- Status: local CLI + optional Windows GUI MVP with MP4 transcription, structured editorial selection, global/composite montage, safe framing, subtitle correction, and progress reporting.
- Primary platform: Windows 11 + Git Bash.
- Reference runtime: Python 3.11 + NVIDIA RTX 4070 12 GB.
- Processing policy: local/offline by default.
- License: MIT.

## Product objective

Generate several usable 9:16 reels from a long-form Xplore Swiss TV video, with optional human validation before rendering.

## Current pipeline

```text
MP4/SRT/YouTube
  -> TranscriptionProvider
  -> TranscriptDocument schema v1
  -> transcript chunks
  -> Ollama per-chunk candidate proposals
  -> optional full-transcript composite proposals
  -> pause/cue boundary refinement with sentence-complete extension
  -> local or Ollama ranking
  -> human or automatic selection
  -> optional PySceneDetect shot analysis
  -> framing plan: crop or fit-blur per shot
  -> embedded-text analysis and subtitle placement
  -> contextual subtitle correction + packaged dictionary
  -> FFmpeg render + subtitle burn + YouTube end card
  -> optional DaVinci XML timelines referencing original media
  -> render report
```

The optional PySide6 GUI starts the same CLI pipeline through `QProcess`; it owns no media-processing logic.

## Stable decisions

- Windows + Git Bash remains the primary runtime.
- Processing stays local by default.
- SRT/YouTube compatibility is preserved.
- WhisperX, PySceneDetect, OpenCV, and PySide6 remain optional and lazily loaded where practical.
- Expensive stages use explicit caches or local timing history.
- Refactor before adding another major responsibility to `analyzer.py` or `renderer.py`.
- Render failures are explicit; no silent cloud or subtitle-free fallback.
- Root `run_*` scripts are local-only and excluded from Git/archive.
- Generated subtitle text is never intentionally truncated.
- Existing source text and ambiguous two-person shots favour full-frame `fit-blur` preservation over aggressive cropping.

## Current defaults

- transcription: `auto`;
- WhisperX: `large-v3`, French, batch size 4;
- spoken boundaries: `auto`, with up to 2 seconds extension for a complete sentence;
- Ollama: `qwen3:4b`, `think=false`, JSON Schema structured outputs;
- candidates: 5 per chunk + 3 full-transcript composite proposals in hybrid mode;
- composition: `hybrid`;
- ranking: Ollama;
- CLI crop: `smart`; GUI crop: `scene-smart`;
- embedded text/title cards: `fit-blur`;
- two similarly important people: `fit-blur`;
- subtitle correction: contextual Ollama with built-in French/Nord-vaudois dictionary;
- subtitle position: `auto`;
- subtitle typography: maximum 72 px, balanced to at most two lines with width-safe reduction;
- end card: 1.5 seconds, `Voir sur YouTube`;
- output: 1080x1920, H.264/AAC; successful render intermediates are cleaned by default;
- subtitle fallback without burn: disabled;
- GUI timing history: enabled under local application data;
- GUI DaVinci XML export: enabled by default.

## Version 0.8.1 delivered

- one Final Cut Pro 7 XML timeline per reel, referencing the original video/audio source ranges;
- composite selections become consecutive source clips in a vertical 1080x1920 timeline;
- standalone `xml` command plus GUI checkbox and `--davinci-xml`;
- XML paths recorded in reel metadata and render report;
- refreshed card-based PySide6 interface with clearer source, settings, progress, ETA, actions, and logs;
- GUI style isolated in `gui_style.py`; XML generation isolated in `davinci_xml.py`;
- 64 passing tests with PySide6 installed.

## Version 0.8.0 delivered

- successful reel folders keep only final MP4, subtitles, caption, metadata, and correction cache;
- render intermediates remain available on failure or with `--keep-render-intermediates`;
- larger 72 px subtitles with balanced width-safe layout and 48 px horizontal margins;
- subtitle layout extracted to `subtitle_layout.py`;
- valid Ollama corrections no longer leave raw-response files;
- conservative dangling-relative grammar repair and correction-cache schema bump;
- all 0.7 framing, complete-sentence, dictionary, and editorial safeguards retained;
- 58 passing tests, with GUI smoke conditional on PySide6.

## Known limitations

- Existing-text detection is lightweight OpenCV analysis, not OCR; `--subtitle-position top|bottom` remains available for manual override.
- Active-speaker audio/face localisation is not implemented. Two-person shots preserve both people.
- Full-transcript montage is skipped when the transcript exceeds a conservative local-model context limit.
- No aesthetic/B-roll scoring yet.
- No music workflow yet.

## Next validation

Run a real Xplore report with quality mode, then inspect:

- `selected_reels.json` for strong, non-generic angles;
- each reel `metadata.json` for `subtitle_position`, `subtitle_layout_analysis`, framing reasons, and source segments;
- `subtitles.srt`/`subtitles.ass` for complete text and proper nouns;
- `render_report.json` for warnings and successful MP4 files.
