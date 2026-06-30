# Working agreement for coding assistants

This file defines how to continue Reelmaker when the project archive is uploaded to ChatGPT or another coding assistant.

## First response after loading the project

1. Read `PROJECT_MANIFEST.md`, `ROADMAP.md`, `docs/ARCHITECTURE.md`, `README.md`, and the tests.
2. Inspect the relevant code before proposing changes.
3. Summarize the current state in at most five lines.
4. Ask only the strategic questions required to choose the next iteration. Usually:
   - What single user-visible objective should this iteration achieve?
   - What result will count as accepted?
   - Are new heavy dependencies acceptable for this iteration?
   - Must the current YouTube-subtitle workflow remain fully compatible?
5. Present a short implementation plan and obtain validation of the objective before modifying code, unless the user explicitly says to proceed immediately.

Do not ask again for information already present in the project files or conversation.

## Iteration rules

- Implement one coherent vertical slice at a time.
- Keep Windows + Git Bash as the primary runtime.
- Keep processing local by default; no paid/cloud API dependency without explicit approval.
- Preserve current CLI behaviour unless the validated objective changes it.
- Add or update tests with every behaviour change.
- Run `bash scripts/check_project.sh` before delivering an iteration.
- Run `bash createTarGz.sh` when preparing the complete project archive for the next conversation.
- Update `PROJECT_MANIFEST.md`, `ROADMAP.md`, and `CHANGELOG.md` when state or decisions change.
- Give the complete modified module when presenting code, or clearly label any excerpt/partial file.

## Anti-spaghetti rules

- `cli.py` orchestrates; it must not contain transcription, scoring, vision, or FFmpeg algorithms.
- External systems are adapters: YouTube/yt-dlp, WhisperX, Ollama, OpenCV, FFmpeg.
- Core data exchanged between stages uses typed dataclasses and versioned JSON.
- A feature must not directly reach into another feature's internal files. Use explicit functions/protocols.
- Do not mix a broad refactor with a feature unless the refactor is a small prerequisite.
- Prefer dependency injection over global configuration.
- Keep fallbacks explicit and visible in reports; never silently degrade quality.

## Refactoring checkpoints

Propose a dedicated refactoring iteration when one of these becomes true:

- a module owns more than one major responsibility;
- a new provider requires copy/paste conditionals;
- cache/output formats change without a version boundary;
- tests need extensive mocking of internal details;
- `analyzer.py` or `renderer.py` must absorb another major subsystem.

Before running such a refactor, explain the concrete stability benefit and ask the user to validate the objective. Avoid architecture rewrites for their own sake.

## Current strategic direction

The next major capability is direct MP4 input with local transcription. The preferred design is a `TranscriptionProvider` boundary with:

- existing subtitle-file/YouTube provider;
- new WhisperX provider;
- optional faster-whisper fallback later.

WhisperX should be introduced behind an optional dependency group and tested first with Python 3.11 on Windows/NVIDIA. Do not place WhisperX imports in the base startup path.
