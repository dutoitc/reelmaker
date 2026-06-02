# Reelmaker

Generate vertical reels from a long video using:

- a **YouTube URL** for high-quality subtitles/transcript;
- a **local video file** for clean rendering;
- **Ollama** for local AI candidate selection;
- **FFmpeg** for vertical cuts, ASS burned subtitles, and optional YouTube end cards.

Version **0.2.0** focuses on making the MVP usable in real runs: safer resume/cache, longer reel boundaries, bottom captions, Windows/Git Bash console safety, and optional basic face-centered crop.

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

Optional, only if you want `--crop-mode face`:

```bash
pip install opencv-python
```

OpenCV face mode is deliberately basic: it detects **frontal faces**, not full people, and computes one static horizontal crop for the whole reel. If it fails, Reelmaker falls back to centered crop.

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
  --source-video "/c/Users/cedric/Videos/source.mp4" \
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
  --subtitle-font-size 64 \
  --subtitle-margin-v 220 \
  --end-card-seconds 2.0 \
  --episode-title "Titre de l'episode YouTube" \
  --output-dir "output/my-video"
```

## What changed in 0.2.0

| Area | Change |
|---|---|
| Selection | If the shortlist has 10 candidates and target is 10, Reelmaker selects them automatically. No more “choose 10 among 10”. |
| Encoding | Candidate display is ASCII-safe by default on Windows to avoid mojibake in Git Bash. JSON files remain UTF-8. Set `REELMAKER_UNICODE_CONSOLE=1` to display accents. |
| Duration | Default minimum reel duration is now 18s, target duration 22s. Short LLM candidates are expanded to nearby subtitle boundaries. |
| Audio cuts | End times are extended with post-padding and following cues to reduce cut-off phrases. |
| Subtitles | Burned subtitles now use ASS, bottom-aligned, larger, with outline. Default margin: `--subtitle-margin-v 220`. |
| Subtitle artefacts | Long overlapping YouTube subtitle cues are filtered to avoid one caption staying on screen while another changes. |
| End card | Optional final card: `--end-card-seconds 2.0 --episode-title "..."`. |
| Vertical crop | Default remains centered. Optional basic face crop: `--crop-mode face` with `opencv-python`. |

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
  --source-video "/c/Users/cedric/Videos/source.mp4" \
  --subtitle-file "output/my-video/subtitles/VIDEO_ID.fr.srt" \
  --selected-reels "output/my-video/selected_reels.json" \
  --end-card-seconds 2.0 \
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
| `--subtitle-font-size` | 64 | burned caption size |
| `--subtitle-margin-v` | 220 | bottom caption margin; larger = higher |
| `--crop-mode` | `center` | use `face` for optional OpenCV face crop |
| `--end-card-seconds` | 0 | 0 disables final YouTube card |
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
