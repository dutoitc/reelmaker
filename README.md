# Reelmaker

Generate vertical reels from a long video using:

- a **YouTube URL** for high-quality subtitles/transcript;
- a **local video file** for clean rendering;
- **Ollama** for local AI candidate selection;
- **FFmpeg** for vertical cuts, ASS burned subtitles, and optional YouTube end cards.

Version **0.2.2** keeps the output-quality work from 0.2.1 and adds the cleanup, tests, documentation, and packaging needed for a public experimental repository.

## Current workflow

```text
YouTube URL + local video
→ extract/cached YouTube subtitles with yt-dlp
→ split transcript into chunks
→ Ollama proposes reel candidates per chunk
→ local boundary refinement expands short cuts to phrase/subtitle boundaries
→ local ranking creates a shortlist
→ human validates reels, unless shortlist <= target count
→ FFmpeg renders 9:16 MP4 reels with bottom subtitles
→ optional final YouTube call-to-action card
```

## Requirements

Install these tools and make sure they are available in `PATH`:

- Python 3.10+
- FFmpeg
- Ollama
- Git Bash on Windows
- yt-dlp dependency installed by the Python package

Recommended:

```bash
ollama pull qwen3:4b
```

Optional, for smarter vertical crop with `--crop-mode smart`, `face`, or `motion`:

```bash
pip install -e ".[vision]"
# or
pip install -r requirements-vision.txt
```

The smart crop is lightweight: it detects frontal faces when possible, otherwise it estimates the active visual area from motion. It does **not** truly identify the active speaker from audio. If detection fails, Reelmaker falls back to centered crop.

## Install

From Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

## Run: recommended mode

Copy `examples/run_reelmaker.sh`, adapt the paths, then run it.

```bash
bash examples/run_reelmaker.sh
```

Or directly:

```bash
python -m reelmaker all \
  --youtube-url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --source-video "/c/Users/YourName/Videos/source.mp4" \
  --ollama-url "http://localhost:11434" \
  --model "qwen3:4b" \
  --subtitle-langs "fr.*,fr" \
  --target-count 10 \
  --shortlist-count 20 \
  --candidates-per-chunk 3 \
  --chunk-seconds 300 \
  --ranking-mode local \
  --ollama-num-predict 1024 \
  --min-duration 18 \
  --target-duration 22 \
  --max-duration 60 \
  --subtitle-font-size 60 \
  --subtitle-margin-v 150 \
  --subtitle-wrap-width 23 \
  --subtitle-correction basic \
  --crop-mode smart \
  --end-card-seconds 3.0 \
  --end-card-style short \
  --youtube-cta "Suite sur YouTube" \
  --end-card-comment-text "Voir commentaire" \
  --episode-title "Titre de l'episode YouTube" \
  --output-dir "output/my-video"
```

## What changed in 0.2.2

| Area | Change |
|---|---|
| Repository | Added clean Git rules, CI tests, project checks, ChatGPT packaging, roadmap, and architecture guardrails. |
| End card | Shorter default card: `Suite sur YouTube` + `Voir commentaire`. Use `--end-card-style title` if you also want the episode title. |
| Subtitles | Defaults are lower and more compact: font 60, margin 150, max 2 lines, narrower wrapping. |
| Subtitle correction | New `--subtitle-correction basic|ollama|off`. `basic` is conservative and fast. `ollama` corrects only selected reel subtitles and caches the result. |
| Vertical crop | New default `--crop-mode smart`: faces first, then motion, then center. `face` and `motion` are also available. |
| Person visibility | Multiple faces are grouped when possible so the 9:16 crop tries to keep both people visible. |
| Selection | If the shortlist has 10 candidates and target is 10, Reelmaker selects them automatically. |
| Duration/audio | Short LLM candidates are expanded to nearby subtitle boundaries and post-padding reduces cut-off phrases. |

## Resume / cache

Reelmaker resumes previous runs by default.

It reuses:

- existing subtitle files in `output/.../subtitles/`;
- `output/.../logs/ollama_chunk_001.txt` if it can parse it;
- `output/.../logs/ollama_chunk_001.candidates.json` if already available;
- local ranking instead of rerunning a slow Ollama ranking.

To force a full recomputation:

```bash
--force-ollama
```

To disable resume/cache:

```bash
--no-resume
```

## Commands

### Extract subtitles only

```bash
python -m reelmaker subtitles \
  --youtube-url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output-dir "output/my-video"
```

### Analyze only, no rendering

```bash
python -m reelmaker analyze \
  --youtube-url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --ollama-url "http://localhost:11434" \
  --model "qwen3:4b" \
  --ranking-mode local \
  --output-dir "output/my-video"
```

### Render from an existing selection

```bash
python -m reelmaker render \
  --source-video "/c/Users/YourName/Videos/source.mp4" \
  --subtitle-file "output/my-video/subtitles/VIDEO_ID.fr.srt" \
  --selected-reels "output/my-video/selected_reels.json" \
  --crop-mode smart \
  --subtitle-correction basic \
  --end-card-seconds 3.0 \
  --end-card-style short \
  --youtube-cta "Suite sur YouTube" \
  --end-card-comment-text "Voir commentaire" \
  --episode-title "Titre de l'episode YouTube" \
  --output-dir "output/my-video"
```

## Output structure

```text
output/my-video/
  subtitles/
  logs/
    ollama_chunk_001.txt
    ollama_chunk_001.candidates.json
  transcript.txt
  transcript.json
  transcript_chunks.json
  candidates.json
  shortlist.json
  selected_reels.json
  reels/
    R01/
      R01.mp4
      R01_content.mp4      # when end card is enabled
      R01_end_card.mp4     # when end card is enabled
      subtitles.srt
      subtitles.ass
      metadata.json
      caption.txt
    R02/
      ...
```

## Useful tuning

| Parameter | Default | Meaning |
|---|---:|---|
| `--model` | `qwen3:4b` | fast local default |
| `--target-count` | 10 | final reels |
| `--shortlist-count` | 20 | candidates shown for validation |
| `--chunk-seconds` | 300 | transcript block size |
| `--candidates-per-chunk` | 3 | max proposals per block |
| `--ranking-mode` | `local` | avoids a slow extra LLM call |
| `--min-duration` | 18 | shortest reel after refinement |
| `--target-duration` | 22 | preferred short reel duration |
| `--max-duration` | 60 | longest reel |
| `--post-padding` | 1.2 | seconds kept after last subtitle cue |
| `--subtitle-font-size` | 60 | burned caption size |
| `--subtitle-margin-v` | 150 | bottom caption margin; larger = higher |
| `--subtitle-correction` | `basic` | use `ollama` for contextual cleanup |
| `--subtitle-max-lines` | 2 | keeps subtitles readable |
| `--end-card-style` | `short` | `title` shows the episode title too |
| `--crop-mode` | `smart` | faces first, then motion, then center |
| `--end-card-seconds` | 0 | 0 disables final YouTube card; 3.0 recommended |
| `--crf` | 20 | lower = better/larger MP4 |

## YouTube subtitle robustness

The safest default is:

```bash
--subtitle-langs "fr.*,fr"
```

Avoid adding `en.*` unless you need English fallback, because each extra language/translation track increases the number of YouTube requests. If extraction becomes unstable, update yt-dlp and install `deno`.

## Notes

- Local source video is preferred: better quality, less download time, no YouTube recompression.
- YouTube subtitles are used only as transcript and timing source.
- Shorts/Reels/TikTok should usually be 15–30s. This tool defaults around 18–22s for MVP testing.

## Development checks

```bash
pip install -e ".[dev]"
bash scripts/check_project.sh
```

GitHub Actions runs the base unit tests on Python 3.10, 3.12, and 3.13. FFmpeg, Ollama, yt-dlp network access, and GPU workflows remain manual integration checks.

## Create a clean archive for ChatGPT

```bash
bash scripts/package_project.sh
```

The generated archive excludes virtual environments, output videos, caches, bytecode, and local media. On the next conversation, upload it and say **“on fait la suite”**. The assistant should follow `AGENTS.md`, ask the strategic questions needed for one iteration, and validate the objective before changing code.

## Next milestone

Direct MP4 input with local WhisperX transcription is planned behind a `TranscriptionProvider` boundary. The current YouTube/SRT workflow remains the compatibility path. See `ROADMAP.md` and `docs/ARCHITECTURE.md`.
