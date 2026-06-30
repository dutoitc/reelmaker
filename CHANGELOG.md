# Changelog

## 0.2.3 — 2026-06-30

- Added root `createTarGz.sh` for a complete, clean ChatGPT upload archive.
- Excluded generated output, caches, build artifacts, secrets, and local media from that archive.
- Removed personal names from documentation, license attribution, and package metadata.

## 0.2.2 — 2026-06-30

- Removed generated Python bytecode from the distributable project.
- Added `.gitignore`, `.gitattributes`, GitHub Actions tests, and dev dependencies.
- Added `scripts/check_project.sh` and `scripts/package_project.sh`.
- Added coding-assistant workflow, roadmap, and architecture guardrails.
- Aligned direct `OllamaClient` defaults with the CLI defaults.
- Reassigned candidate IDs after cached chunks are merged to prevent duplicate IDs.
- Removed a personal Windows path from the example script.
- Scoped YouTube subtitle/video cache selection to the requested video ID.
- Kept basic subtitle cleanup for items omitted by an Ollama correction response.

## 0.2.1

- Smarter static vertical crop, subtitle correction, compact end cards, and safer subtitle display.

## 0.2.0

- Candidate boundary refinement, local ranking, resume/cache support, and interactive selection.
