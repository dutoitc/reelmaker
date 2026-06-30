# Reelmaker

Generate several vertical reels from a long video with local tools:

- **WhisperX** for local MP4 transcription and word timestamps;
- **Ollama** for local reel candidate selection;
- **FFmpeg** for 9:16 rendering, subtitles, and optional end cards;
- **OpenCV** for optional smart crop hints.

Version **0.4.0** improves reel beginnings and endings by scoring WhisperX word pauses and punctuation. SRT/VTT and YouTube subtitles remain supported through a cue-based fallback.

## Recommended environment

- Windows 11, 64-bit;
- Git Bash;
- Python **3.11**;
- FFmpeg in `PATH`;
- Ollama;
- NVIDIA GPU recommended for WhisperX. CPU mode is supported but slower.

## Initialize Windows + Git Bash

### 1. Install Python 3.11

Install the 64-bit version from [python.org](https://www.python.org/downloads/windows/), including the Python launcher.

Verify in Git Bash:

```bash
py -3.11 --version
```

### 2. Install FFmpeg

FFmpeg publishes source code and links to Windows builds on its [official download page](https://ffmpeg.org/download.html). Download a Windows build, extract it, and add its `bin` directory to the Windows `PATH`.

Close and reopen Git Bash, then verify:

```bash
ffmpeg -version
ffprobe -version
```

### 3. Install Ollama

Install Ollama from the [official Windows page](https://ollama.com/download/windows). It runs in the background and exposes its local API on port `11434`.

```bash
ollama --version
ollama pull qwen3:4b
ollama run qwen3:4b "Réponds uniquement: OK"
```

### 4. Install CUDA for WhisperX GPU mode

WhisperX currently requests the **CUDA 12.8 toolkit** for GPU acceleration. Install it from [NVIDIA CUDA Downloads](https://developer.nvidia.com/cuda-downloads), then restart Windows if requested.

Verify the NVIDIA driver:

```bash
nvidia-smi
```

CUDA is not required for CPU-only transcription.

### 5. Create the project environment

From the Reelmaker directory in Git Bash:

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,vision,transcription]"
```

The `transcription` extra installs the stable WhisperX dependency declared by the project. The `vision` extra enables the current smart-crop functions. The `dev` extra installs the test suite.

Verify the environment:

```bash
python -c "import whisperx; print('WhisperX OK')"
python -c "import torch; print('Torch:', torch.__version__); print('CUDA:', torch.cuda.is_available(), torch.version.cuda)"
python -m reelmaker --help
bash scripts/check_project.sh
```

Expected for GPU mode:

```text
CUDA: True ...
```

### Base installation without WhisperX

For the existing SRT/YouTube workflow only:

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[vision]"
```

### CPU-only WhisperX

Install normally, then select CPU explicitly. A smaller model is recommended:

```bash
python -m reelmaker transcribe \
  --source-video "/c/Videos/reportage.mp4" \
  --whisper-device cpu \
  --whisper-compute-type int8 \
  --whisper-model small \
  --output-dir "output/reportage"
```

## Direct MP4 workflow

### 1. Transcribe only

```bash
python -m reelmaker transcribe \
  --source-video "/c/Videos/reportage.mp4" \
  --output-dir "output/reportage"
```

With only `--source-video`, `--transcription auto` selects WhisperX. The first run downloads the Whisper and French alignment models. Processing remains local after the required models are cached.

Generated files:

```text
output/reportage/
  transcript.json   # cues, word timestamps and cache fingerprints
  transcript.srt
  transcript.txt
```

### 2. Analyze and render

```bash
python -m reelmaker all \
  --source-video "/c/Videos/reportage.mp4" \
  --model "qwen3:4b" \
  --target-count 10 \
  --ranking-mode local \
  --crop-mode smart \
  --output-dir "output/reportage"
```

## Natural cut refinement

Default mode:

```bash
--boundary-mode auto
```

Behaviour:

1. use WhisperX word timestamps and measured pauses when available;
2. combine pauses, sentence punctuation, cue boundaries and optional speaker changes;
3. fall back to SRT/VTT cue boundaries when word timestamps are unavailable;
4. write the method, score and reasons into `candidates.json` and `shortlist.json`.

Available modes:

| Mode | Behaviour |
|---|---|
| `auto` | word pauses first, cue fallback |
| `words` | prefer word timestamps; cue fallback if unavailable |
| `cues` | use subtitle cue boundaries only |
| `off` | keep Ollama timecodes unchanged, useful for comparison |

Example before/after comparison:

```bash
python -m reelmaker analyze \
  --source-video "/c/Videos/reportage.mp4" \
  --boundary-mode off \
  --output-dir "output/baseline"

python -m reelmaker analyze \
  --source-video "/c/Videos/reportage.mp4" \
  --boundary-mode auto \
  --output-dir "output/refined"
```

Candidate metadata example:

```json
{
  "boundary_method": "words",
  "boundary_score": 82.5,
  "boundary_reasons": [
    "start:pause_0.74s",
    "start:previous_sentence_end",
    "end:sentence_end",
    "end:pause_1.10s"
  ]
}
```

## Useful WhisperX parameters

| Parameter | Default | Usage |
|---|---:|---|
| `--whisper-model` | `large-v3` | quality-oriented French transcription |
| `--whisper-language` | `fr` | use `auto` for language detection |
| `--whisper-device` | `auto` | selects CUDA when available |
| `--whisper-compute-type` | `auto` | float16 on CUDA, int8 on CPU |
| `--whisper-batch-size` | `4` | reduce to 2 or 1 if VRAM is insufficient |
| `--force-transcription` | off | ignore the fingerprinted transcript cache |

For a 12 GB NVIDIA GPU, start with `large-v3`, `float16`, batch size 4. If memory is insufficient, try batch size 2, then 1; after that try `--whisper-compute-type int8` or a smaller model.

## Existing YouTube/SRT workflow

YouTube subtitles with a local high-quality video:

```bash
python -m reelmaker all \
  --youtube-url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --source-video "/c/Videos/reportage.mp4" \
  --subtitle-langs "fr.*,fr" \
  --output-dir "output/reportage"
```

Local subtitle file:

```bash
python -m reelmaker all \
  --subtitle-file "/c/Videos/reportage.fr.srt" \
  --source-video "/c/Videos/reportage.mp4" \
  --output-dir "output/reportage"
```

Selection rule for `--transcription auto`:

1. supplied SRT/VTT: use it;
2. supplied YouTube URL: extract its subtitles;
3. local MP4 only: use WhisperX.

Force a source with:

```bash
--transcription subtitles
--transcription whisperx
```

## Troubleshooting

### `ffmpeg: command not found`

The extracted FFmpeg `bin` directory is not in the Windows `PATH`, or Git Bash was not reopened after the change.

### `WhisperX is not installed`

```bash
source .venv/Scripts/activate
pip install -e ".[transcription]"
```

### Torch reports `CUDA: False`

Check `nvidia-smi`, the CUDA 12.8 installation, and that the active virtual environment contains the expected Torch build. CPU mode remains available with `--whisper-device cpu`.

### GPU out of memory

Try in this order:

```bash
--whisper-batch-size 2
--whisper-batch-size 1
--whisper-compute-type int8
--whisper-model medium
```

### Ollama connection error

Open the Ollama Windows application, then verify:

```bash
ollama list
ollama run qwen3:4b "OK"
```

## Cache

`transcript.json` is reused only when these still match:

- provider;
- sampled source-file fingerprint;
- transcription settings;
- WhisperX package version.

Invalidate it with `--force-transcription`.

Ollama candidate caches remain under `output/.../logs/` and can be invalidated with `--force-ollama`.

## Main output structure

```text
output/reportage/
  subtitles/
  logs/
  transcript.json
  transcript.srt
  transcript.txt
  transcript_chunks.json
  candidates.json
  shortlist.json
  selected_reels.json
  reels/
    R01/
      R01.mp4
      subtitles.srt
      subtitles.ass
      metadata.json
      caption.txt
```

## Development checks

```bash
source .venv/Scripts/activate
pip install -e ".[dev]"
bash scripts/check_project.sh
```

The base CI test suite does not load a real WhisperX model. The adapter uses an injected fake module; GPU processing remains a Windows integration test.

## Create a clean archive for ChatGPT

```bash
bash createTarGz.sh
```

This creates `reelmaker.tgz` at the project root without output, media, caches, environments, build files or secrets.
