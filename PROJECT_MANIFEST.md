# Project Manifest — Reelmaker

## Objective

Create a reproducible local tool that generates around 10 vertical reels from a long video. The target platforms are Instagram Reels, TikTok, and optionally YouTube Shorts. The intended use is to turn existing long-form CAPStv/XploreSwissTV-style videos into short, interesting clips that can redirect attention toward the full YouTube video.

## Core idea

Use the best available transcript from YouTube, but render from the local source video.

Input:

- YouTube URL: used mainly to extract high-quality subtitles/transcript.
- Local source video: preferred rendering source for clean quality.
- Optional fallback: download the YouTube video if no local source is supplied.
- Ollama URL and model: local LLM for candidate detection.

Output:

- 10 vertical MP4 reels, 1080x1920.
- Burned subtitles when FFmpeg supports the subtitles filter.
- One metadata JSON and one caption text file per reel.
- Intermediate JSON files for transcript, candidates, shortlist, and final selections.

## Technical stack

Language: Python.

Reason:

- Best fit for yt-dlp and FFmpeg orchestration.
- Simple Ollama HTTP calls.
- Fast MVP iteration.
- Easy GitHub publication.
- Future binary distribution possible with PyInstaller or Nuitka.

Dependencies:

- Python 3.10+
- yt-dlp Python package
- FFmpeg installed externally
- Ollama installed externally

No heavy framework is used. The MVP intentionally avoids Typer, Pydantic, MoviePy, Whisper, or UI dependencies.

## Recommended Ollama model

Default model: `qwen3:4b`.

Reason:

- Faster for iterative local use.
- Good enough for transcript-based candidate detection.
- Reduces the runtime problem observed with `qwen3:8b`.

Quality model: `qwen3:8b`.

Use it when candidate quality matters more than runtime, or only after the workflow is stable.

Potential later model: `qwen3:14b`, slower and not recommended for the MVP loop.

## AI strategy

Do not ask the model once for 10 final reels from the full transcript. That is too fragile.

Current pipeline:

1. Load SRT/VTT transcript.
2. Split transcript into chunks of about 5 minutes.
3. For each chunk, ask Ollama for a small number of candidate reels.
4. Save each chunk response and parsed candidates immediately.
5. Merge all candidates.
6. Rank locally by score and warning penalties by default.
7. Show the shortlist to the human user.
8. User validates 10 by typing candidate numbers.
9. Render the selected reels.

This strategy reduces context drift and keeps the local model focused. It also avoids a slow and fragile second LLM ranking pass.

## Resume/cache strategy

Resume is enabled by default.

The tool reuses:

- existing useful subtitle files in `output/.../subtitles/`;
- previous raw Ollama chunk logs: `output/.../logs/ollama_chunk_001.txt`;
- parsed chunk candidates: `output/.../logs/ollama_chunk_001.candidates.json`;
- local ranking, which does not call Ollama.

Important CLI flags:

- `--force-ollama`: ignore cached Ollama chunks and recompute.
- `--no-resume`: disable resume/cache.
- `--ranking-mode local`: default, fast, deterministic.
- `--ranking-mode ollama`: optional second LLM pass, slower and more fragile.

## Prompt constraints

Every prompt should force these rules:

- Use only the transcript.
- Do not invent facts.
- Keep exact timestamps.
- Return valid JSON only.
- Prefer standalone clips.
- Prefer strong first 3 seconds.
- Avoid duplicate ideas.
- Penalize too short, too long, or context-dependent candidates.

## Important design decisions

Local video is preferred over YouTube video download:

- Better quality.
- No additional long download.
- No extra YouTube compression.
- More stable rendering source.

YouTube transcript is preferred over DaVinci transcription:

- User observed that DaVinci subtitle quality is poor.
- User observed that YouTube subtitle quality is excellent.

Human validation remains in the workflow:

- The LLM proposes candidates.
- The local ranker orders them.
- The user validates the final 10 reels.
- This avoids low-quality or contextually wrong reels.

Rendering is done by FFmpeg:

- 9:16 vertical crop/scale.
- MP4 H.264 output.
- Burned subtitles if supported.
- SRT retained for each reel.

## Current CLI commands

Main command:

```bash
python -m reelmaker all \
  --youtube-url "URL" \
  --source-video "LOCAL_VIDEO.mp4" \
  --ollama-url "http://localhost:11434" \
  --model "qwen3:4b" \
  --ranking-mode local \
  --output-dir "output/my-video"
```

Other commands:

- `subtitles`: extract subtitles only.
- `analyze`: generate candidates, shortlist, and selected reels JSON.
- `render`: render from an existing `selected_reels.json`.

## Known limitations

- No automatic face/object tracking for vertical crop yet. Current crop is centered.
- Subtitle styling is basic.
- Hooks are text suggestions; no separate visual title card yet.
- The local LLM can still produce imperfect JSON; parsing includes a loose extractor but failures are logged.
- FFmpeg subtitle burning may fail on some builds; the renderer retries without burned subtitles.
- YouTube subtitle extraction may require the video to have subtitles available and accessible.
- YouTube can return HTTP 429 when too many subtitle/translation tracks are requested. Default subtitle language selector is `fr.*,fr`.
- Current yt-dlp YouTube extraction increasingly benefits from a JavaScript runtime such as `deno`.

## Next logical improvements

1. Add smart crop zones: center, left, right, or manual crop per reel.
2. Add title overlay / first-frame hook text.
3. Add optional YouTube Shorts metadata export.
4. Add `reels_plan.json` import/export for DaVinci timelines later.
5. Add basic GUI or local web UI for validating the shortlist.
6. Add a mode that uses YouTube Analytics retention data if available.
7. Add binary packaging with PyInstaller or Nuitka.

## Project style

Prefer:

- Small readable modules.
- JSON as the interchange format.
- Reproducible shell scripts.
- Manual override at every important step.
- Conservative AI prompts.
- Practical output over complex architecture.

## Notes version 0.1.3

- Default model changed to `qwen3:4b` for speed.
- Default ranking changed to local ranking; Ollama ranking remains optional with `--ranking-mode ollama`.
- Added resume/cache for chunk analysis.
- Added per-chunk parsed candidate files: `ollama_chunk_XXX.candidates.json`.
- Reuses existing subtitle files instead of redownloading them on every run.
- Fixed Windows console output for Unicode/UTF-8 issues.
- Replaced the warning symbol in the interactive shortlist with ASCII text.
- Reduced default `--candidates-per-chunk` to 3 and `--ollama-num-predict` to 1024.
