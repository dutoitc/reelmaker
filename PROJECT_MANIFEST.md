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

- Around 10 vertical MP4 reels, 1080x1920.
- Burned ASS subtitles near the bottom of the frame.
- Optional final YouTube call-to-action card.
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
- Optional: `opencv-python` and `numpy` for `--crop-mode smart`, `face`, or `motion`

No heavy framework is used. The MVP intentionally avoids Typer, Pydantic, MoviePy, Whisper, or UI dependencies. OpenCV/numpy are optional; without them, smart crop falls back to centered crop.

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
7. Expand candidate boundaries to nearby subtitle cues to avoid 4-12s clips and mid-sentence audio cuts.
8. Show the shortlist to the human user.
9. If shortlist size is <= target count, select all automatically.
10. Otherwise, user validates the final reels by typing candidate numbers.
11. Render the selected reels.

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
- Burned ASS subtitles if supported.
- SRT and ASS subtitles retained for each reel.
- Optional end card rendered as a short black 1080x1920 segment with CTA text.

Vertical crop:

- Default: `--crop-mode smart`.
- `smart` uses OpenCV if installed: frontal faces first, then motion, then center fallback.
- `face` forces face detection only.
- `motion` uses frame differences to follow the visually active area.
- Multiple faces are grouped when possible to avoid cutting one person out.
- This is still a static crop per reel, not true speaker detection or dynamic person tracking.

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

- `--crop-mode smart` improves framing but does not truly identify who is speaking. It computes one static crop per reel; no dynamic speaker alternation yet.
- Subtitle styling is practical but not a branded motion-graphics system.
- Hooks are text suggestions; no separate animated title card yet.
- The local LLM can still produce imperfect JSON; parsing includes a loose extractor but failures are logged.
- FFmpeg subtitle burning may fail on some builds; the renderer retries without burned subtitles.
- YouTube subtitle extraction may require the video to have subtitles available and accessible.
- YouTube can return HTTP 429 when too many subtitle/translation tracks are requested. Default subtitle language selector is `fr.*,fr`.
- Current yt-dlp YouTube extraction increasingly benefits from a JavaScript runtime such as `deno`.

## Next logical improvements

1. Add manual crop zones per reel: center, left, right, custom x.
2. Add better person tracking via a modern detector if dependency size is acceptable.
3. Add title overlay / first-frame hook text.
4. Add optional YouTube Shorts metadata export.
5. Add `reels_plan.json` import/export for DaVinci timelines later.
6. Add basic GUI or local web UI for validating the shortlist.
7. Add a mode that uses YouTube Analytics retention data if available.
8. Add binary packaging with PyInstaller or Nuitka.

## Project style

Prefer:

- Small readable modules.
- JSON as the interchange format.
- Reproducible shell scripts.
- Manual override at every important step.
- Conservative AI prompts.
- Practical output over complex architecture.

## Notes version 0.2.1

- Default crop mode is now `smart`: face detection, then motion detection, then center fallback.
- Added optional dependency group `vision` and `requirements-vision.txt`.
- Added `--subtitle-correction off|basic|ollama`; `basic` is default, `ollama` corrects selected reel captions with context and cache.
- End card is now intentionally short by default: `Suite sur YouTube` + `Voir commentaire`.
- Added `--end-card-style short|title|full|none` and `--end-card-comment-text`.
- Subtitle defaults are more compact: font 60, bottom margin 150, max 2 lines, wrap width 23.

## Notes version 0.2.0

- Kept `qwen3:4b` as default model and local ranking as default.
- Added candidate boundary refinement using subtitle cues.
- Changed defaults to `--min-duration 18`, `--target-duration 22`, `--max-duration 60`.
- If shortlist size is <= target count, the tool selects all candidates automatically.
- Console shortlist display is ASCII-safe on Windows by default; JSON remains UTF-8.
- Added ASS subtitles with bottom alignment, larger font, outline and margin controls.
- Added cleanup of overlapping long YouTube subtitle cues for reel segments.
- Added optional end card: `--end-card-seconds`, `--episode-title`, `--youtube-cta`.
- Added optional basic face crop mode with OpenCV: `--crop-mode face`.

## Notes version 0.1.3

- Default model changed to `qwen3:4b` for speed.
- Default ranking changed to local ranking; Ollama ranking remains optional with `--ranking-mode ollama`.
- Added resume/cache for chunk analysis.
- Added per-chunk parsed candidate files: `ollama_chunk_XXX.candidates.json`.
- Reuses existing subtitle files instead of redownloading them on every run.
- Fixed Windows console output for Unicode/UTF-8 issues.
- Replaced the warning symbol in the interactive shortlist with ASCII text.
- Reduced default `--candidates-per-chunk` to 3 and `--ollama-num-predict` to 1024.
