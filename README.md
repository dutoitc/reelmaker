# Reelmaker

Generate several vertical reels from a long video with local tools:

- **WhisperX** for local MP4 transcription and word timestamps;
- **Ollama** for local editorial selection, montage proposals, and subtitle correction;
- **FFmpeg** for 9:16 rendering, subtitles, and optional end cards;
- **OpenCV** for local face/motion framing hints;
- **PySceneDetect** for optional shot detection and per-shot framing;
- **PySide6** for the optional Windows desktop interface.

Version **0.6.0** adds a Windows GUI, multi-run time estimates, composite reels, safer wide-shot framing, stronger spoken boundaries, and stricter subtitle/render validation.

## Recommended environment

- Windows 11, 64-bit;
- Git Bash;
- Python **3.11**;
- FFmpeg in `PATH`;
- Ollama;
- NVIDIA GPU recommended for WhisperX. CPU mode is supported but slower.

## Initialize Windows + Git Bash

### 1. Install Python 3.11

Install the 64-bit version from <https://www.python.org/downloads/windows/>, including the Python launcher.

```bash
py -3.11 --version
```

### 2. Install FFmpeg

Download a Windows build from the links on <https://ffmpeg.org/download.html>, extract it, and add its `bin` directory to the Windows `PATH`.

Close and reopen Git Bash, then verify:

```bash
ffmpeg -version
ffprobe -version
```

### 3. Install Ollama

Install Ollama from <https://ollama.com/download/windows>, then:

```bash
ollama --version
ollama pull qwen3:4b
ollama run qwen3:4b --think=false "Réponds uniquement: OK"
```

### 4. Install CUDA for WhisperX GPU mode

For the current WhisperX environment, install the **CUDA 12.8 toolkit** from <https://developer.nvidia.com/cuda-downloads>.

```bash
nvidia-smi
nvcc --version
```

CUDA is not required for CPU-only transcription.

### 5. Create the complete project environment

From the Reelmaker directory in Git Bash:

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,vision,transcription,gui]"
```

Extras:

| Extra | Content |
|---|---|
| `transcription` | WhisperX and its transcription dependencies |
| `vision` | OpenCV and PySceneDetect |
| `gui` | PySide6 desktop interface |
| `dev` | pytest and project checks |

Verify:

```bash
python -c "import whisperx; print('WhisperX OK')"
python -c "import torch; print('Torch:', torch.__version__); print('CUDA:', torch.cuda.is_available(), torch.version.cuda)"
python -c "import scenedetect; print('PySceneDetect:', scenedetect.__version__)"
python -m reelmaker --help
bash scripts/check_project.sh
```

Expected for GPU mode:

```text
CUDA: True ...
```

If Torch reports a CPU build such as `2.8.0+cpu`, reinstall its CUDA 12.8 wheels in the active environment:

```bash
python -m pip uninstall -y torch torchvision torchaudio
python -m pip install \
  torch==2.8.0 \
  torchvision==0.23.0 \
  torchaudio==2.8.0 \
  --index-url https://download.pytorch.org/whl/cu128
```

### Base installation without WhisperX or GUI

For the SRT/YouTube CLI workflow only:

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[vision]"
```

## Windows desktop interface

Launch from Git Bash:

```bash
bash startGui.sh
```

Or double-click:

```text
startGui.bat
```

Alternative after activating the environment:

```bash
reelmaker-gui
```

The interface provides:

- MP4 and output-directory selection;
- Ollama model, target count, crop mode, composition mode, and subtitle correction;
- current stage and stage progress;
- overall progress;
- elapsed time;
- estimated remaining time for the current stage;
- live console logs;
- cancel and open-output buttons.

The GUI remains a thin layer over the CLI. Processing logic stays in the existing modules and the GUI starts `python -m reelmaker all` as a subprocess.

## Multi-run time estimates

Time history is useful rather than cosmetic: WhisperX, Ollama, scene detection, and FFmpeg have different speeds on each machine.

Reelmaker stores local timing samples in:

```text
%LOCALAPPDATA%\Reelmaker\timing_history.json
```

On non-Windows systems it uses:

```text
~/.reelmaker/timing_history.json
```

It records the last 20 normalized samples per configuration:

- WhisperX seconds per source-video second, separated by provider/model/device/compute type;
- Ollama seconds per transcript chunk, separated by model and composition mode;
- PySceneDetect seconds per source-video second;
- FFmpeg seconds per rendered source second, separated by crop mode/preset/FPS.

The median is used for the next run. Estimates are therefore rough on the first run and improve after several similar runs. The file contains timing data only and is not included in project archives.

## Direct MP4 workflow

### Transcribe only

```bash
python -m reelmaker transcribe \
  --source-video "/c/Videos/reportage.mp4" \
  --output-dir "output/reportage"
```

With only `--source-video`, `--transcription auto` selects WhisperX. The first run downloads the Whisper and French alignment models.

Generated files:

```text
output/reportage/
  transcript.json
  transcript.srt
  transcript.txt
```

### Analyze and render

```bash
python -m reelmaker all \
  --source-video "/c/Videos/reportage.mp4" \
  --model "qwen3:4b" \
  --target-count 6 \
  --ranking-mode local \
  --composition-mode hybrid \
  --crop-mode scene-smart \
  --subtitle-correction ollama \
  --output-dir "output/reportage"
```

Runtime dependencies are checked before expensive transcription. For example, `scene-smart` now fails immediately when PySceneDetect is missing instead of analyzing the full video and failing during rendering.

If no MP4 is produced, the command exits with an error and points to `render_report.json` and the corresponding `ffmpeg.error.txt` files.

## Editorial composition

Default mode:

```bash
--composition-mode hybrid
```

`hybrid` allows Ollama to propose either:

- one continuous extract;
- or a montage of two or three non-contiguous passages about the same subject.

Composite proposals must form a progression such as hook → explanation → conclusion. Their source intervals are stored in `segments`, then rendered in editorial order with subtitles remapped to the continuous output timeline.

Use the previous behaviour when required:

```bash
--composition-mode contiguous
```

Composite generation currently works within each transcript analysis chunk. A future global editorial pass may combine distant passages across the complete programme.

## Natural spoken boundaries

Default mode:

```bash
--boundary-mode auto
```

Reelmaker combines:

1. WhisperX word timestamps and measured pauses;
2. sentence punctuation;
3. subtitle cue boundaries;
4. optional speaker changes;
5. a strong preference for a complete final sentence.

Composite reels are refined segment by segment. A candidate receives `boundary_incomplete_end` when a confident natural ending cannot be found within the duration limit.

Available modes:

| Mode | Behaviour |
|---|---|
| `auto` | word pauses first, cue fallback |
| `words` | prefer word timestamps; cue fallback if unavailable |
| `cues` | subtitle cue boundaries only |
| `off` | keep Ollama timecodes unchanged |

## Scene-aware and wide-shot framing

Fast static mode:

```bash
--crop-mode smart
```

Per-shot mode for reportages:

```bash
--crop-mode scene-smart
```

`scene-smart` uses PySceneDetect, writes `scenes.json`, and recalculates framing for each detected shot.

Framing safety rules in 0.6.0:

- one clearly dominant face can be isolated;
- close faces can be kept in the same crop;
- two similarly important people spread across a horizontal shot use a **fit-blur** layout so neither face is cut;
- wide landscapes, monuments, slides, or full-screen visuals without a reliable subject also use fit-blur instead of an arbitrary destructive crop;
- uncertain motion is no longer enough to force a crop.

Fit-blur preserves the complete horizontal frame over a blurred vertical background.

Current limitation: Reelmaker does not yet localize the active speaker from the audio. In an ambiguous two-person shot it deliberately preserves both people instead of guessing and cutting the wrong person.

Scene parameters:

| Parameter | Default | Usage |
|---|---:|---|
| `--scene-threshold` | `27` | lower detects more cuts; raise for false cuts |
| `--scene-min-frames` | `15` | ignores very short shots/transitions |
| `--force-scene-detection` | off | rebuild `scenes.json` |
| `--scene-detection off` | — | one static smart decision |

Test detection only:

```bash
python -m reelmaker scenes \
  --source-video "/c/Videos/reportage.mp4" \
  --output-dir "output/reportage"
```

## Subtitle quality and completeness

The CLI and GUI now default to:

```bash
--subtitle-correction ollama
```

The correction pass uses neighbouring cues as context to repair likely ASR mistakes, accents, apostrophes, agreements, and punctuation without changing meaning. If Ollama correction fails, conservative basic cleanup is used and the error is kept beside the reel.

Long captions are split into several timed cues instead of being truncated. All source segments in a composite reel are remapped to the final timeline.

By default, subtitle burn failures are errors: Reelmaker will not silently deliver a video without subtitles. The previous fallback is available only when explicitly requested:

```bash
--allow-subtitle-fallback
```

Disable subtitles entirely with:

```bash
--no-burn-subtitles
```

## Useful WhisperX parameters

| Parameter | Default | Usage |
|---|---:|---|
| `--whisper-model` | `large-v3` | quality-oriented French transcription |
| `--whisper-language` | `fr` | use `auto` for detection |
| `--whisper-device` | `auto` | selects CUDA when available |
| `--whisper-compute-type` | `auto` | float16 on CUDA, int8 on CPU |
| `--whisper-batch-size` | `4` | reduce to 2 or 1 if VRAM is insufficient |
| `--force-transcription` | off | ignore transcript cache |

CPU example:

```bash
python -m reelmaker transcribe \
  --source-video "/c/Videos/reportage.mp4" \
  --whisper-device cpu \
  --whisper-compute-type int8 \
  --whisper-model small \
  --output-dir "output/reportage"
```

## YouTube/SRT workflow

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

1. supplied SRT/VTT;
2. supplied YouTube URL;
3. local MP4 only → WhisperX.

## Cache

- `transcript.json`: source and WhisperX settings fingerprint;
- `scenes.json`: source and scene settings fingerprint;
- Ollama candidate caches: `output/.../logs/`, separated between contiguous and hybrid analysis;
- corrected subtitles: fingerprinted by cues, reel selection, title, model, and schema;
- timing history: outside the project under the local application-data directory.

Force recalculation with:

```bash
--force-transcription
--force-ollama
--force-scene-detection
--force-subtitle-correction
```

## Troubleshooting

### `PySceneDetect is not installed`

```bash
source .venv/Scripts/activate
pip install -e ".[vision]"
python -c "import scenedetect; print(scenedetect.__version__)"
```

### `PySide6 is not installed`

```bash
source .venv/Scripts/activate
pip install -e ".[gui]"
```

### `WhisperX is not installed`

```bash
source .venv/Scripts/activate
pip install -e ".[transcription]"
```

### Torch reports `CUDA: False`

Verify that the active environment contains the CUDA build, not a package ending in `+cpu`.

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"
```

### GPU out of memory

Try:

```bash
--whisper-batch-size 2
--whisper-batch-size 1
--whisper-compute-type int8
--whisper-model medium
```

### TorchCodec warning

The current WhisperX path preloads audio and can continue even when Pyannote warns that TorchCodec decoding is unavailable. Treat it as a warning unless a later traceback explicitly fails audio decoding or diarization.

### Ollama connection or structured-output error

```bash
ollama list
ollama run qwen3:4b --think=false "Réponds uniquement: OK"
```

Update Ollama if an HTTP 400 reports unsupported `format` or `think` fields.

## Main output structure

```text
output/reportage/
  subtitles/
  logs/
  transcript.json
  transcript.srt
  transcript.txt
  scenes.json
  transcript_chunks.json
  candidates.json
  shortlist.json
  selected_reels.json
  reels/
    render_report.json
    R01/
      R01.mp4
      subtitles.srt
      subtitles.ass
      subtitles_corrected.json
      metadata.json
      caption.txt
```

## Local run scripts and project archive

Root files matching `run_*` are ignored by Git and excluded from `reelmaker.tgz`. The maintained example under `examples/` remains part of the project.

Create the clean full archive for a future ChatGPT iteration:

```bash
bash createTarGz.sh
```

The command creates `reelmaker.tgz` at the project root without output, media, local run scripts, caches, environments, build files, or secrets.

## Development checks

```bash
source .venv/Scripts/activate
pip install -e ".[dev,vision,transcription,gui]"
bash scripts/check_project.sh
```

The full environment currently runs 45 tests. The GUI smoke test is skipped automatically when PySide6 is not installed.
