from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any

from .models import ReelSelection, SubtitleCue
from .subtitles import cues_for_segment, write_srt
from .timecode import format_hms
from .utils import run_command, write_json
from .vision import CropHint, detect_face_crop_hint


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    centiseconds = int(round(seconds * 100))
    cs = centiseconds % 100
    total_seconds = centiseconds // 100
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("\\", "\\\\")
    text = text.replace("{", r"\{").replace("}", r"\}")
    return text


def _wrap_ass(text: str, *, width: int = 28, max_lines: int = 2) -> str:
    wrapped = textwrap.wrap(_ass_escape(text), width=width, break_long_words=False, replace_whitespace=False)
    if not wrapped:
        return ""
    if len(wrapped) > max_lines:
        wrapped = wrapped[:max_lines]
        wrapped[-1] = wrapped[-1].rstrip(" .,") + "..."
    return r"\N".join(wrapped)


def write_ass_subtitles(
    path: Path,
    cues: list[SubtitleCue],
    *,
    font_size: int = 64,
    margin_v: int = 220,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,4,0,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header.rstrip()]
    for cue in cues:
        text = _wrap_ass(cue.text)
        if not text:
            continue
        lines.append(f"Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},Reel,,0,0,0,,{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_end_card_ass(
    path: Path,
    *,
    cta: str,
    episode_title: str,
    duration: float,
    youtube_url: str = "",
) -> None:
    parts = [cta.strip() or "Video complete sur YouTube"]
    if episode_title.strip():
        parts.append(episode_title.strip())
    if youtube_url.strip():
        parts.append("Lien dans la description / sur la chaine")
    text = r"\N".join(_wrap_ass(part, width=24, max_lines=2) for part in parts if part.strip())
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Card,Arial,72,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,4,0,5,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    path.write_text(header + f"Dialogue: 0,0:00:00.00,{_ass_time(duration)},Card,,0,0,0,,{text}\n", encoding="utf-8")


def _scale_crop_filter(crop_hint: CropHint | None) -> str:
    if crop_hint and crop_hint.crop_x is not None:
        return f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:{crop_hint.crop_x}:0,setsar=1"
    return "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"


def _video_filter(*, burn_subtitles: bool, crop_hint: CropHint | None) -> str:
    base = _scale_crop_filter(crop_hint)
    if not burn_subtitles:
        return f"{base},format=yuv420p"
    return f"{base},subtitles=subtitles.ass,format=yuv420p"


def _render_end_card(
    *,
    reel_dir: Path,
    output_video: Path,
    duration: float,
    cta: str,
    episode_title: str,
    youtube_url: str,
    fps: int,
    crf: int,
    preset: str,
) -> bool:
    ass_path = reel_dir / "end_card.ass"
    write_end_card_ass(ass_path, cta=cta, episode_title=episode_title, duration=duration, youtube_url=youtube_url)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=1080x1920:r={fps}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        f"{duration:.3f}",
        "-vf",
        "subtitles=end_card.ass,format=yuv420p",
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
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(output_video.name),
    ]
    return run_command(cmd, cwd=reel_dir, check=False).returncode == 0


def _concat_videos(*, reel_dir: Path, parts: list[Path], output_video: Path) -> bool:
    concat_path = reel_dir / "concat.txt"
    concat_path.write_text("\n".join(f"file '{part.name}'" for part in parts) + "\n", encoding="utf-8")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path.name),
        "-c",
        "copy",
        str(output_video.name),
    ]
    return run_command(cmd, cwd=reel_dir, check=False).returncode == 0


def render_reel(
    *,
    source_video: Path,
    selection: ReelSelection,
    all_cues: list[SubtitleCue],
    output_dir: Path,
    burn_subtitles: bool = True,
    subtitle_font_size: int = 64,
    subtitle_margin_v: int = 220,
    crop_mode: str = "center",
    fps: int = 25,
    end_card_seconds: float = 0.0,
    episode_title: str = "",
    youtube_cta: str = "Video complete sur YouTube",
    youtube_url: str = "",
    crf: int = 20,
    preset: str = "medium",
) -> dict[str, Any]:
    reel_dir = output_dir / selection.id
    reel_dir.mkdir(parents=True, exist_ok=True)

    local_cues = cues_for_segment(all_cues, selection.start, selection.end)
    srt_path = reel_dir / "subtitles.srt"
    ass_path = reel_dir / "subtitles.ass"
    write_srt(srt_path, local_cues)
    write_ass_subtitles(ass_path, local_cues, font_size=subtitle_font_size, margin_v=subtitle_margin_v)

    metadata_path = reel_dir / "metadata.json"
    metadata = selection.to_dict()
    metadata["episode_title"] = episode_title
    metadata["youtube_url"] = youtube_url
    metadata["end_card_seconds"] = end_card_seconds
    write_json(metadata_path, metadata)

    caption_path = reel_dir / "caption.txt"
    caption_parts = [selection.hook, selection.title]
    if episode_title:
        caption_parts.append(f"Video complete sur YouTube : {episode_title}")
    if youtube_url:
        caption_parts.append(youtube_url)
    caption_parts.append("#reels #tiktok #shorts")
    caption_path.write_text("\n\n".join(part for part in caption_parts if part) + "\n", encoding="utf-8")

    output_video = reel_dir / f"{selection.id}.mp4"
    content_video = reel_dir / (f"{selection.id}_content.mp4" if end_card_seconds > 0 else f"{selection.id}.mp4")
    end_card_video = reel_dir / f"{selection.id}_end_card.mp4"
    duration = max(0.1, selection.end - selection.start)

    crop_hint = CropHint(None, "center")
    if crop_mode == "face":
        crop_hint = detect_face_crop_hint(source_video=source_video, start=selection.start, duration=duration)

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
            _video_filter(burn_subtitles=with_subtitles, crop_hint=crop_hint),
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(content_video.name),
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
        "content_video": str(content_video),
        "subtitles": str(srt_path),
        "ass_subtitles": str(ass_path),
        "metadata": str(metadata_path),
        "caption": str(caption_path),
        "crop_mode": crop_mode,
        "crop_hint": crop_hint.reason,
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

    if end_card_seconds > 0:
        ok_card = _render_end_card(
            reel_dir=reel_dir,
            output_video=end_card_video,
            duration=end_card_seconds,
            cta=youtube_cta,
            episode_title=episode_title or selection.title,
            youtube_url=youtube_url,
            fps=fps,
            crf=crf,
            preset=preset,
        )
        if ok_card:
            ok_concat = _concat_videos(reel_dir=reel_dir, parts=[content_video, end_card_video], output_video=output_video)
            if not ok_concat:
                result["warnings"].append("end_card_concat_failed_content_only")
                if content_video != output_video:
                    output_video.write_bytes(content_video.read_bytes())
        else:
            result["warnings"].append("end_card_render_failed_content_only")
            if content_video != output_video:
                output_video.write_bytes(content_video.read_bytes())

    return result


def render_reels(
    *,
    source_video: Path,
    selections: list[ReelSelection],
    all_cues: list[SubtitleCue],
    output_dir: Path,
    burn_subtitles: bool = True,
    subtitle_font_size: int = 64,
    subtitle_margin_v: int = 220,
    crop_mode: str = "center",
    fps: int = 25,
    end_card_seconds: float = 0.0,
    episode_title: str = "",
    youtube_cta: str = "Video complete sur YouTube",
    youtube_url: str = "",
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
                subtitle_font_size=subtitle_font_size,
                subtitle_margin_v=subtitle_margin_v,
                crop_mode=crop_mode,
                fps=fps,
                end_card_seconds=end_card_seconds,
                episode_title=episode_title,
                youtube_cta=youtube_cta,
                youtube_url=youtube_url,
                crf=crf,
                preset=preset,
            )
        )
    write_json(output_dir / "render_report.json", results)
    return results
