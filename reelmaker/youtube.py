from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .utils import run_command

_SUBTITLE_SUFFIXES = {".srt", ".vtt"}
_MIN_USEFUL_SUBTITLE_BYTES = 200
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _youtube_video_id(youtube_url: str) -> str | None:
    parsed = urlparse(youtube_url.strip())
    host = (parsed.hostname or "").lower()
    candidate = ""

    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/", 1)[0]
    elif host.endswith("youtube.com"):
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
                candidate = parts[1]

    return candidate if _YOUTUBE_ID_RE.fullmatch(candidate) else None


def _subtitle_files(output_dir: Path, *, video_id: str | None = None) -> list[Path]:
    files = [p for p in output_dir.glob("*") if p.is_file() and p.suffix.lower() in _SUBTITLE_SUFFIXES]
    if video_id:
        files = [p for p in files if p.name.startswith(f"{video_id}.")]
    return files


def _looks_french(name: str) -> bool:
    return any(token in name for token in [".fr", "-fr", "fr-", "fr_", "french"])


def _looks_english(name: str) -> bool:
    return any(token in name for token in [".en", "-en", "en-", "en_", "english"])


def _subtitle_score(path: Path) -> tuple[int, int, float]:
    """Score downloaded subtitles.

    yt-dlp can create tiny placeholder subtitle files for unavailable translated tracks
    (observed around 35 bytes). Prefer useful French SRT files, then size.
    """
    name = path.name.lower()
    size = path.stat().st_size

    score = 0
    if size >= _MIN_USEFUL_SUBTITLE_BYTES:
        score += 100
    else:
        score -= 100

    if path.suffix.lower() == ".srt":
        score += 20

    if _looks_french(name):
        score += 50
    if ".fr.srt" in name:
        score += 12
    if ".fr-orig." in name or ".fr_orig." in name:
        score += 10
    if ".fr-ch." in name:
        score += 6
    if _looks_english(name):
        score -= 30

    # Larger subtitle files usually mean the track actually contains cues.
    return score, size, path.stat().st_mtime


def _best_subtitle_file(
    output_dir: Path,
    *,
    before: set[Path] | None = None,
    video_id: str | None = None,
) -> Path | None:
    all_files = _subtitle_files(output_dir, video_id=video_id)
    if before:
        new_files = [p for p in all_files if p not in before]
        candidates = new_files or all_files
    else:
        candidates = all_files
    if not candidates:
        return None
    return max(candidates, key=_subtitle_score)


def extract_youtube_subtitles(
    youtube_url: str,
    output_dir: Path,
    *,
    subtitle_langs: str = "fr.*,fr",
) -> Path:
    """Download YouTube subtitles/auto-subtitles as SRT/VTT and return the best file.

    Important: yt-dlp may successfully download useful subtitles, then fail later on
    another requested language with HTTP 429. In that case, keep the useful subtitle
    already present instead of aborting the whole Reelmaker run.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    video_id = _youtube_video_id(youtube_url)

    existing = _best_subtitle_file(output_dir, video_id=video_id) if video_id else None
    if existing and existing.stat().st_size >= _MIN_USEFUL_SUBTITLE_BYTES:
        print(f"Using cached subtitle file: {existing}", flush=True)
        return existing

    before = set(output_dir.glob("*"))

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "--ignore-errors",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        subtitle_langs,
        "--sub-format",
        "srt/vtt/best",
        "--convert-subs",
        "srt",
        "-o",
        str(output_dir / "%(id)s.%(ext)s"),
        youtube_url,
    ]
    result = run_command(cmd, check=False)

    subtitle_path = _best_subtitle_file(output_dir, before=before, video_id=video_id)
    if subtitle_path:
        if result.returncode != 0:
            print(
                "WARNING: yt-dlp returned an error, but a usable subtitle file was downloaded. "
                f"Continuing with: {subtitle_path}",
                flush=True,
            )
        if subtitle_path.stat().st_size < _MIN_USEFUL_SUBTITLE_BYTES:
            print(
                "WARNING: selected subtitle file is very small; it may be empty or incomplete: "
                f"{subtitle_path}",
                flush=True,
            )
        return subtitle_path

    if result.returncode != 0:
        raise RuntimeError(
            "No subtitle file downloaded. yt-dlp failed. "
            "Try --subtitle-file, reduce --subtitle-langs to fr.*,fr, update yt-dlp, "
            "or add a JS runtime such as deno for current YouTube extraction."
        )

    raise RuntimeError("No subtitle file downloaded. Check that YouTube has subtitles or try --subtitle-file.")


def download_youtube_video(youtube_url: str, output_dir: Path) -> Path:
    """Optional fallback: download the YouTube video. Local source is preferable for quality."""
    output_dir.mkdir(parents=True, exist_ok=True)
    before = set(output_dir.glob("*"))
    video_id = _youtube_video_id(youtube_url)
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "-o",
        str(output_dir / "%(id)s.%(ext)s"),
        youtube_url,
    ]
    run_command(cmd)
    all_videos = [
        p
        for p in output_dir.glob("*")
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
    ]
    new_videos = [p for p in all_videos if p not in before]
    matching_videos = [p for p in all_videos if video_id and p.name.startswith(f"{video_id}.")]
    videos = sorted(new_videos or matching_videos, key=lambda p: p.stat().st_mtime, reverse=True)
    if not videos:
        raise RuntimeError("No video downloaded.")
    return videos[0]


def copy_local_subtitle(subtitle_file: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / subtitle_file.name
    if subtitle_file.resolve() != target.resolve():
        shutil.copy2(subtitle_file, target)
    return target
