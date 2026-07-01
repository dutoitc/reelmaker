# Working agreement for coding assistants

This file defines how to continue Reelmaker when its archive is uploaded to ChatGPT or another coding assistant.

## First response after loading the project

1. Read `PROJECT_MANIFEST.md`, `ROADMAP.md`, `docs/ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`, and the tests.
2. Inspect relevant implementation and any supplied real-run logs/reports.
3. Summarize the state in at most five lines.
4. Ask only strategic questions required to select one iteration.
5. Obtain validation of a dedicated refactor objective before modifying code, unless the user explicitly orders immediate implementation.

Do not ask again for information already present in project files or conversation.

## Iteration rules

- Implement one coherent vertical slice at a time.
- Keep Windows + Git Bash as the primary runtime.
- Keep processing local by default.
- Preserve CLI behaviour unless the validated objective changes it.
- Keep the GUI as a thin subprocess/progress layer; no media logic in `gui.py`.
- Add or update tests for every behaviour change.
- Run `bash scripts/check_project.sh` before delivery.
- Build the wheel/sdist when packaging changes.
- Run `bash createTarGz.sh` for the next complete upload archive.
- Update manifest, roadmap, changelog, README, and architecture when applicable.
- When showing code, provide the complete modified module or mark excerpts clearly.

## Anti-spaghetti rules

- `cli.py` orchestrates only.
- External systems remain adapters: yt-dlp, WhisperX, Ollama, OpenCV/PySceneDetect, FFmpeg, PySide6.
- Shared data uses typed dataclasses and versioned JSON.
- Features communicate through explicit public functions/protocols.
- Do not mix a broad refactor with a feature unless it is a small prerequisite.
- Prefer dependency injection over globals.
- Never silently degrade to a paid/cloud service.
- Never silently emit a subtitle-free or missing video as success.

## Refactoring checkpoints

Propose a dedicated refactoring iteration when:

- a module owns more than one major responsibility;
- a provider addition requires copy/paste conditionals;
- a persisted schema changes without a version boundary;
- tests require extensive internal mocking;
- `analyzer.py` or `renderer.py` would absorb another subsystem;
- active speaker tracking, B-roll, or music would require significant logic in existing modules.

Explain the concrete stability benefit and obtain objective validation before a dedicated refactor.

## Current strategic direction

Version 0.8.1 adds DaVinci Resolve source-edit XML timelines and a cleaner card-based GUI while retaining the 0.8 compact deliverables and subtitle safeguards.

Preferred sequence:

1. validate one continuous and one composite XML timeline in DaVinci Resolve, including original audio and relinking;
2. validate real Xplore output in quality + hybrid + scene-smart + automatic subtitle-position mode;
3. inspect `selected_reels.json`, subtitle files, each reel `metadata.json`, and `render_report.json`;
4. tune text-detection, subtitle typography, dictionary, boundary, and global-montage thresholds only from observed examples;
5. next choose active-speaker tracking or aesthetic/B-roll scoring;
6. refactor renderer responsibilities before adding music.

Known limitations: existing-text detection is not OCR; active-speaker localisation is not implemented; ambiguous two-person shots preserve both people with fit-blur.
