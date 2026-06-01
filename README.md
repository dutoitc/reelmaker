# Reelmaker

Generate vertical reels from a long video using:

- a **YouTube URL** for high-quality subtitles/transcript;
- a **local video file** for clean rendering;
- **Ollama** for local AI candidate selection;
- **FFmpeg** for vertical cuts and burned subtitles.

The default model is now `qwen3:4b` to keep the MVP usable on a local PC. For better quality, use `qwen3:8b` on selected videos.

## Current MVP workflow

```text
YouTube URL + local video
→ extract/cached YouTube subtitles with yt-dlp
→ split transcript into chunks
→ Ollama proposes reel candidates per chunk
→ local ranking creates a shortlist
→ human validates 10 reels
→ FFmpeg renders 9:16 MP4 reels with subtitles
```

## Requirements

Install these tools and make sure they are available in `PATH`:

- Python 3.10+
- FFmpeg
- Ollama
- Git Bash on Windows
- yt-dlp dependency installed by the Python package

Recommended for current YouTube extraction reliability:

- install/update `deno`, because recent yt-dlp YouTube extraction increasingly expects a JavaScript runtime;
- keep `yt-dlp` updated;
- start with French subtitles only: `--subtitle-langs "fr.*,fr"`.

Install the fast default Ollama model:

```bash
ollama pull qwen3:4b
```

Optional higher-quality model:

```bash
ollama pull qwen3:8b
```

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
  --output-dir "output/my-video"
```

The program displays the shortlist. Choose 10 by typing numbers, for example:

```text
1,2,4,7,8,9,11,12,15,18
```

Press `Enter` to accept the top 10.

## Resume / cache

Reelmaker now resumes previous runs by default.

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

## Run without local video

This is more flexible but slower and usually lower quality than your local master:

```bash
python -m reelmaker all \
  --youtube-url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --download-video \
  --ollama-url "http://localhost:11434" \
  --model "qwen3:4b" \
  --output-dir "output/my-video"
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
      subtitles.srt
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
| `--min-duration` | 15 | shortest reel |
| `--max-duration` | 75 | longest reel |
| `--temperature` | 0.2 | lower = more stable |
| `--num-ctx` | 16384 | Ollama context size |
| `--ollama-num-predict` | 1024 | maximum generated tokens per request |
| `--crf` | 20 | lower = better/larger MP4 |

## YouTube subtitle robustness

If YouTube returns `HTTP Error 429` while downloading one of several subtitle variants, Reelmaker keeps a usable subtitle file already downloaded instead of aborting.

The safest default is:

```bash
--subtitle-langs "fr.*,fr"
```

Avoid adding `en.*` unless you need English fallback, because each extra language/translation track increases the number of YouTube requests. If extraction becomes unstable, update yt-dlp and install `deno`.

## Notes

- Local source video is preferred: better quality, less download time, no YouTube recompression.
- YouTube subtitles are used only as transcript and timing source.
- If subtitle burning fails, rendering retries without burned subtitles and keeps the `.srt` file.
- The JSON files are meant to be editable manually before rendering.
