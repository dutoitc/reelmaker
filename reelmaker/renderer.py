from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ReelSelection, SubtitleCue
from .subtitles import cues_for_segment, write_srt
from .timecode import format_hms
from .utils import run_command, write_json


def _subtitle_filter(enabled: bool) -> str:
    base = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if not enabled:
        return base
    # The subtitles file is generated inside the reel directory and ffmpeg is run with cwd=reel_dir.
    style = (
        "FontName=Arial,"
        "FontSize=13,"
        "PrimaryColour=&H00FFFFFF&,"
        "OutlineColour=&H00000000&,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=120"
    )
    return f"{base},subtitles=subtitles.srt:force_style='{style}'"


def render_reel(
    *,
    source_video: Path,
    selection: ReelSelection,
    all_cues: list[SubtitleCue],
    output_dir: Path,
    burn_subtitles: bool = True,
    crf: int = 20,
    preset: str = "medium",
) -> dict[str, Any]:
    reel_dir = output_dir / selection.id
    reel_dir.mkdir(parents=True, exist_ok=True)

    local_cues = cues_for_segment(all_cues, selection.start, selection.end)
    srt_path = reel_dir / "subtitles.srt"
    write_srt(srt_path, local_cues)

    metadata_path = reel_dir / "metadata.json"
    write_json(metadata_path, selection.to_dict())

    caption_path = reel_dir / "caption.txt"
    caption_path.write_text(
        f"{selection.hook}\n\n{selection.title}\n\n#reels #tiktok #shorts\n",
        encoding="utf-8",
    )

    output_video = reel_dir / f"{selection.id}.mp4"
    duration = max(0.1, selection.end - selection.start)

    def build_cmd(with_subtitles: bool) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-ss",
            f"{selection.start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source_video.resolve()),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            _subtitle_filter(with_subtitles),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output_video.name),
        ]

    result = {
        "id": selection.id,
        "candidate_id": selection.candidate_id,
        "title": selection.title,
        "hook": selection.hook,
        "start": format_hms(selection.start),
        "end": format_hms(selection.end),
        "duration": round(duration, 3),
        "video": str(output_video),
        "subtitles": str(srt_path),
        "metadata": str(metadata_path),
        "caption": str(caption_path),
        "status": "ok",
        "warnings": [],
    }

    completed = run_command(build_cmd(burn_subtitles), cwd=reel_dir, check=False)
    if completed.returncode != 0 and burn_subtitles:
        result["warnings"].append("subtitle_burn_failed_retry_without_subtitles")
        completed = run_command(build_cmd(False), cwd=reel_dir, check=False)

    if completed.returncode != 0:
        result["status"] = "error"
        result["warnings"].append(f"ffmpeg_exit_{completed.returncode}")
        (reel_dir / "ffmpeg.error.txt").write_text(completed.stdout or "", encoding="utf-8")
    return result


def render_reels(
    *,
    source_video: Path,
    selections: list[ReelSelection],
    all_cues: list[SubtitleCue],
    output_dir: Path,
    burn_subtitles: bool = True,
    crf: int = 20,
    preset: str = "medium",
) -> list[dict[str, Any]]:
    results = []
    for selection in selections:
        print(f"\nRendering {selection.id}: {selection.title}")
        results.append(
            render_reel(
                source_video=source_video,
                selection=selection,
                all_cues=all_cues,
                output_dir=output_dir,
                burn_subtitles=burn_subtitles,
                crf=crf,
                preset=preset,
            )
        )
    write_json(output_dir / "render_report.json", results)
    return results
