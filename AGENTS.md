# Working agreement for coding assistants

This file defines how to continue Reelmaker when its archive is uploaded to ChatGPT or another coding assistant.

## First response after loading the project

1. Read `PROJECT_MANIFEST.md`, `ROADMAP.md`, `docs/ARCHITECTURE.md`, `README.md`, and the tests.
2. Inspect relevant implementation before proposing changes.
3. Summarize the state in at most five lines.
4. Ask only strategic questions required to select one iteration.
5. Obtain validation of the objective before modifying code, unless the user explicitly says to proceed immediately.

Do not ask again for information already present in project files or conversation.

## Iteration rules

- Implement one coherent vertical slice at a time.
- Keep Windows + Git Bash as the primary runtime.
- Keep processing local by default.
- Preserve current CLI behaviour unless the validated objective changes it.
- Add or update tests for every behaviour change.
- Run `bash scripts/check_project.sh` before delivery.
- Run `bash createTarGz.sh` for the next complete upload archive.
- Update `PROJECT_MANIFEST.md`, `ROADMAP.md`, and `CHANGELOG.md`.
- When showing code, provide the complete modified module or mark excerpts clearly.

## Anti-spaghetti rules

- `cli.py` orchestrates only.
- External systems remain adapters: yt-dlp, WhisperX, Ollama, OpenCV, FFmpeg.
- Shared data uses typed dataclasses and versioned JSON.
- Features communicate through explicit public functions/protocols.
- Do not mix a broad refactor with a feature unless it is a small prerequisite.
- Prefer dependency injection over globals.
- Never silently degrade to a paid/cloud service.

## Refactoring checkpoints

Propose a dedicated refactoring iteration when:

- a module owns more than one major responsibility;
- a provider addition requires copy/paste conditionals;
- a persisted schema changes without a version boundary;
- tests require extensive internal mocking;
- `analyzer.py` or `renderer.py` would absorb another subsystem.

Explain the concrete stability benefit and obtain objective validation before a dedicated refactor.

## Current strategic direction

Version 0.5.1 stabilizes Qwen 3 through Ollama structured outputs and explicit `think=false`. Scene-aware framing still requires real-video validation before aesthetic scoring or B-roll.

Preferred sequence:

- compare `--crop-mode smart` and `scene-smart` on representative Xplore footage;
- inspect false/missed cuts and crop stability;
- tune thresholds only from observed failures;
- consider a stronger face/person detector if framing remains weak;
- keep aesthetic scoring and B-roll outside `renderer.py`.
