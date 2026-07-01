# Reelmaker roadmap

## Releases delivered

### 0.3.0 — direct MP4 transcription

- SRT, YouTube, and WhisperX providers;
- direct MP4 input;
- word timestamps and fingerprinted transcript cache.

### 0.4.0 — safer spoken boundaries

- pause-aware beginnings/endings;
- punctuation and cue fallback;
- `--boundary-mode auto|words|cues|off`.

### 0.5.0 / 0.5.1 — scene framing and reliable Ollama JSON

- PySceneDetect and per-shot framing;
- `scene-smart` rendering;
- `think=false`, structured JSON Schema outputs, and diagnostics.

### 0.6.0 — desktop workflow and first quality safeguards

- PySide6 Windows GUI;
- progress and multi-run ETA history;
- hybrid two/three-passage montage;
- fit-blur, subtitle correction, and explicit render failures.

### 0.7.0 — real-output stabilization and stronger editorial selection

- subtitle text is never truncated;
- automatic subtitle placement away from existing source text;
- title cards and embedded text preserved with fit-blur;
- two-person shots preserve both people;
- French/Nord-vaudois correction dictionary;
- sentence-complete endings with a controlled two-second extension;
- full-transcript composite montage pass;
- stronger impact-oriented generation/ranking;
- quality/fast GUI profile;
- default `Voir sur YouTube` end card.

### 0.8.0 — compact deliverables and subtitle typography

- final reel folders no longer retain content/end-card temporary MP4 files;
- explicit `--keep-render-intermediates` debugging mode;
- larger balanced subtitles with width-safe dynamic sizing;
- dedicated subtitle-layout module;
- raw Ollama subtitle responses kept only on parse failure;
- conservative final grammar repair and correction-cache invalidation.

### 0.8.1 — DaVinci handoff and GUI polish

- one Final Cut Pro 7 XML timeline per reel using original source in/out points;
- vertical 1080x1920 sequence, original audio, composite source clips, and timeline marker;
- standalone `xml` command, CLI flag, GUI default checkbox, metadata/report paths;
- card-based PySide6 layout with clearer progress, ETA, status, actions, and logs.

## Validation gate for 0.8.x

Test at least two real reportages with:

```bash
--composition-mode hybrid
--ranking-mode ollama
--crop-mode scene-smart
--subtitle-position auto
--subtitle-correction ollama
```

Record observations for:

- no generated word missing or replaced by ellipsis;
- no overlay on existing captions/lower thirds;
- title cards and wide graphics fully visible;
- two-person interviews fully visible;
- correct local names;
- complete final sentences;
- editorial strength of continuous and global-composite proposals;
- ETA accuracy after several runs;
- import at least one continuous and one composite XML timeline into DaVinci Resolve, checking source relink, audio, frame rate, and source in/out points.

## Candidate iteration 0.8.1 — tuning from real footage

Only after inspecting output metadata and examples:

- tune OpenCV text-detection thresholds;
- tune subtitle top/bottom margins;
- tune global montage context limit and number of candidates;
- add dictionary entries observed in real transcripts;
- improve diagnostics for rejected/incomplete candidates.

## Candidate iteration 0.9 — active speaker and person tracking

Refactoring checkpoint: create a dedicated tracking subsystem rather than expanding `vision.py` indefinitely.

- stronger face/person detector;
- track people across a shot;
- associate speaker timing with visible people when confidence is high;
- crop the active speaker only at high confidence;
- preserve both people otherwise.

## Candidate iteration 1.0 — beautiful views and B-roll

- representative frames per scene;
- blur/exposure/stability scores;
- semantic relevance between transcript and shots;
- detect and propose strong scenic inserts;
- human validation before automatic insertion.

## Candidate iteration 1.1 — music

Refactor renderer responsibilities first.

- local licensed music library with tags;
- automatic ducking under speech;
- optional beat-aware cuts;
- loudness and rights rules;
- disabled by default until configured.
