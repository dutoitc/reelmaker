from __future__ import annotations

import re
import shutil
import textwrap
from pathlib import Path
from typing import Any, Callable

from .framing import FramingSegment, build_framing_plan
from .models import ReelSelection, SubtitleCue
from .ollama_client import OllamaClient
from .scene_analysis import Scene
from .subtitle_corrector import maybe_correct_cues
from .subtitles import cues_for_segments, split_cues_for_display, write_srt
from .subtitle_layout import _subtitle_ass_layout, _text_width_units, write_ass_subtitles
from .timecode import format_hms
from .utils import run_command, write_json
from .vision import CropHint
from .visual_text import detect_visual_text


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


def _wrap_ass_lines(text: str, *, width: int = 24) -> list[str]:
    return textwrap.wrap(
        _ass_escape(text),
        width=max(8, width),
        break_long_words=False,
        break_on_hyphens=False,
        replace_whitespace=False,
    )


def _wrap_ass(text: str, *, width: int = 24, max_lines: int = 2) -> str:
    # End-card helper. Subtitle layout uses measured, balanced lines below.
    return r"\N".join(_wrap_ass_lines(text, width=width))


def write_end_card_ass(
    path: Path,
    *,
    cta: str,
    episode_title: str,
    duration: float,
    youtube_url: str = "",
    style: str = "short",
    comment_text: str = "Voir commentaire",
) -> None:
    """Write a concise end-card.

    Long end cards are unreadable on Reels/TikTok. The default keeps only a
    clear CTA plus one small hint. The episode title is optional and smaller.
    """
    cta = (cta or "Voir sur YouTube").strip()
    episode_title = episode_title.strip()
    comment_text = (comment_text or "").strip()

    events: list[tuple[str, float, int, str]] = []
    if style == "none":
        events = []
    elif style == "title" and episode_title:
        events = [
            (cta, 0.0, 76, "CardMain"),
            (episode_title, 0.65, 48, "CardTitle"),
            (comment_text, 1.35, 48, "CardSmall"),
        ]
    elif style == "full":
        events = [
            (cta, 0.0, 72, "CardMain"),
            (episode_title, 0.65, 46, "CardTitle"),
            (comment_text, 1.35, 48, "CardSmall"),
        ]
        if youtube_url.strip():
            events.append(("Lien dans la description", 2.0, 40, "CardSmall"))
    else:
        events = [
            (cta, 0.0, 82, "CardMain"),
            (comment_text, 0.75, 54, "CardSmall"),
        ]

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CardMain,Arial,82,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,5,1,5,80,80,80,1
Style: CardTitle,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,0,0,0,0,100,100,0,0,1,4,1,5,90,90,80,1
Style: CardSmall,Arial,54,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,4,1,5,90,90,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header.rstrip()]
    for text, start, _font, style_name in events:
        if not text.strip():
            continue
        width = 18 if style_name == "CardMain" else 26
        max_lines = 1 if style_name != "CardTitle" else 2
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(duration)},"
            f"{style_name},,0,0,0,,{_wrap_ass(text, width=width, max_lines=max_lines)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _scale_crop_filter(crop_hint: CropHint | None) -> str:
    if crop_hint and crop_hint.layout == "fit-blur":
        return (
            "split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,gblur=sigma=28[bg2];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2];"
            "[bg2][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
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
    style: str,
    comment_text: str,
) -> bool:
    ass_path = reel_dir / "end_card.ass"
    write_end_card_ass(
        ass_path,
        cta=cta,
        episode_title=episode_title,
        duration=duration,
        youtube_url=youtube_url,
        style=style,
        comment_text=comment_text,
    )
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
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path.name), "-c", "copy", str(output_video.name)]
    return run_command(cmd, cwd=reel_dir, check=False).returncode == 0



def _content_encode_args(*, fps: int, crf: int, preset: str) -> list[str]:
    return [
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
    ]


def _render_framing_segment(
    *,
    source_video: Path,
    segment: FramingSegment,
    output_path: Path,
    work_dir: Path,
    fps: int,
    crf: int,
    preset: str,
) -> tuple[bool, str]:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{segment.start:.3f}",
        "-t",
        f"{segment.duration:.3f}",
        "-i",
        str(source_video.resolve()),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        _video_filter(burn_subtitles=False, crop_hint=segment.crop_hint),
        *_content_encode_args(fps=fps, crf=crf, preset=preset),
        str(output_path.name),
    ]
    completed = run_command(cmd, cwd=work_dir, check=False)
    return completed.returncode == 0, completed.stdout or ""


def _burn_subtitles_on_video(
    *,
    reel_dir: Path,
    input_video: Path,
    output_video: Path,
    fps: int,
    crf: int,
    preset: str,
) -> tuple[bool, str]:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_video.relative_to(reel_dir)),
        "-vf",
        "subtitles=subtitles.ass,format=yuv420p",
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
        "copy",
        "-movflags",
        "+faststart",
        str(output_video.name),
    ]
    completed = run_command(cmd, cwd=reel_dir, check=False)
    return completed.returncode == 0, completed.stdout or ""


def _render_scene_aware_content(
    *,
    source_video: Path,
    framing_plan: list[FramingSegment],
    reel_dir: Path,
    content_video: Path,
    burn_subtitles: bool,
    fps: int,
    crf: int,
    preset: str,
    allow_subtitle_fallback: bool = False,
) -> tuple[bool, list[str], str]:
    warnings: list[str] = []
    segments_dir = reel_dir / "_scene_segments"
    shutil.rmtree(segments_dir, ignore_errors=True)
    segments_dir.mkdir(parents=True, exist_ok=True)

    parts: list[Path] = []
    for index, segment in enumerate(framing_plan, start=1):
        part = segments_dir / f"part_{index:03d}.mp4"
        ok, log = _render_framing_segment(
            source_video=source_video,
            segment=segment,
            output_path=part,
            work_dir=segments_dir,
            fps=fps,
            crf=crf,
            preset=preset,
        )
        if not ok:
            return False, warnings + [f"scene_segment_{index}_failed"], log
        parts.append(part)

    assembled = segments_dir / "assembled.mp4"
    if not _concat_videos(reel_dir=segments_dir, parts=parts, output_video=assembled):
        return False, warnings + ["scene_concat_failed"], ""

    if burn_subtitles:
        ok, log = _burn_subtitles_on_video(
            reel_dir=reel_dir,
            input_video=assembled,
            output_video=content_video,
            fps=fps,
            crf=crf,
            preset=preset,
        )
        if not ok:
            warnings.append("subtitle_burn_failed")
            if not allow_subtitle_fallback:
                shutil.rmtree(segments_dir, ignore_errors=True)
                return False, warnings, log
            warnings.append("subtitle_fallback_without_burn")
            shutil.copyfile(assembled, content_video)
            if content_video.exists():
                shutil.rmtree(segments_dir, ignore_errors=True)
                return True, warnings, log
            shutil.rmtree(segments_dir, ignore_errors=True)
            return False, warnings, log
    else:
        shutil.copyfile(assembled, content_video)

    shutil.rmtree(segments_dir, ignore_errors=True)
    return True, warnings, ""



def _resolve_subtitle_position(
    *,
    source_video: Path,
    source_segments,
    requested: str,
) -> tuple[str, dict[str, float | int | str]]:
    if requested in {"top", "bottom"}:
        return requested, {"mode": requested, "detected": 0}

    analyses = [
        detect_visual_text(
            source_video=source_video,
            start=segment.start,
            duration=segment.duration,
        )
        for segment in source_segments
        if segment.duration > 0
    ]
    if not analyses:
        return "bottom", {"mode": "auto", "detected": 0}

    top = max(item.top for item in analyses)
    middle = max(item.middle for item in analyses)
    bottom = max(item.bottom for item in analyses)
    total = max(item.total for item in analyses)
    frames = sum(item.frames for item in analyses)
    representative = max(analyses, key=lambda item: item.total)
    position = representative.preferred_subtitle_position
    return position, {
        "mode": "auto",
        "position": position,
        "top": round(top, 4),
        "middle": round(middle, 4),
        "bottom": round(bottom, 4),
        "total": round(total, 4),
        "frames": frames,
    }

def _cleanup_render_artifacts(
    *,
    reel_dir: Path,
    output_video: Path,
    content_video: Path,
    end_card_video: Path,
    keep_intermediates: bool,
) -> None:
    """Remove successful render intermediates while preserving useful assets.

    On failure the files are intentionally kept for diagnosis. On success the
    final MP4, subtitles, caption, metadata, and correction cache remain.
    """
    if keep_intermediates or not output_video.is_file() or output_video.stat().st_size <= 0:
        return
    for path in (
        content_video if content_video != output_video else None,
        end_card_video,
        reel_dir / "concat.txt",
        reel_dir / "end_card.ass",
    ):
        if path is not None:
            path.unlink(missing_ok=True)


def render_reel(
    *,
    source_video: Path,
    selection: ReelSelection,
    all_cues: list[SubtitleCue],
    output_dir: Path,
    burn_subtitles: bool = True,
    subtitle_font_size: int = 72,
    subtitle_margin_v: int = 150,
    subtitle_wrap_width: int = 30,
    subtitle_max_lines: int = 2,
    subtitle_position: str = "auto",
    subtitle_correction: str = "basic",
    correction_dictionary: Path | None = None,
    subtitle_correction_client: OllamaClient | None = None,
    force_subtitle_correction: bool = False,
    crop_mode: str = "smart",
    scenes: list[Scene] | None = None,
    fps: int = 25,
    end_card_seconds: float = 1.5,
    end_card_style: str = "short",
    end_card_comment_text: str = "",
    episode_title: str = "",
    youtube_cta: str = "Voir sur YouTube",
    youtube_url: str = "",
    crf: int = 20,
    preset: str = "medium",
    allow_subtitle_fallback: bool = False,
    keep_render_intermediates: bool = False,
) -> dict[str, Any]:
    reel_dir = output_dir / selection.id
    reel_dir.mkdir(parents=True, exist_ok=True)

    source_segments = selection.source_segments
    local_cues = cues_for_segments(all_cues, [(segment.start, segment.end) for segment in source_segments])
    corrected_cues = maybe_correct_cues(
        local_cues,
        mode=subtitle_correction,
        selection=selection,
        episode_title=episode_title,
        client=subtitle_correction_client,
        cache_path=reel_dir / "subtitles_corrected.json",
        dictionary_path=correction_dictionary,
        force=force_subtitle_correction,
    )
    display_cues = split_cues_for_display(
        corrected_cues,
        max_chars=max(12, subtitle_wrap_width * subtitle_max_lines),
    )
    subtitle_position_resolved, subtitle_layout = _resolve_subtitle_position(
        source_video=source_video,
        source_segments=source_segments,
        requested=subtitle_position,
    )
    srt_path = reel_dir / "subtitles.srt"
    ass_path = reel_dir / "subtitles.ass"
    write_srt(srt_path, display_cues)
    write_ass_subtitles(
        ass_path,
        display_cues,
        font_size=subtitle_font_size,
        margin_v=subtitle_margin_v,
        wrap_width=subtitle_wrap_width,
        max_lines=subtitle_max_lines,
        position=subtitle_position_resolved,
    )

    caption_path = reel_dir / "caption.txt"
    caption_parts = [selection.hook, selection.title]
    if episode_title:
        caption_parts.append(f"Voir sur YouTube : {episode_title}")
    if youtube_url:
        caption_parts.append(youtube_url)
    caption_parts.append("#reels #tiktok #shorts")
    caption_path.write_text("\n\n".join(part for part in caption_parts if part) + "\n", encoding="utf-8")

    output_video = reel_dir / f"{selection.id}.mp4"
    content_video = reel_dir / (f"{selection.id}_content.mp4" if end_card_seconds > 0 else f"{selection.id}.mp4")
    end_card_video = reel_dir / f"{selection.id}_end_card.mp4"
    duration = max(0.1, selection.duration)

    framing_plan: list[FramingSegment] = []
    for source_segment in source_segments:
        framing_plan.extend(
            build_framing_plan(
                source_video=source_video,
                start=source_segment.start,
                end=source_segment.end,
                crop_mode=crop_mode,
                scenes=scenes,
            )
        )
    if not framing_plan and source_segments:
        framing_plan = [
            FramingSegment(
                source_segments[0].start,
                source_segments[0].end,
                CropHint(None, "center_fallback", 0.0),
            )
        ]

    metadata_path = reel_dir / "metadata.json"
    metadata = selection.to_dict()
    metadata["episode_title"] = episode_title
    metadata["youtube_url"] = youtube_url
    metadata["end_card_seconds"] = end_card_seconds
    metadata["end_card_style"] = end_card_style
    metadata["subtitle_correction"] = subtitle_correction
    metadata["subtitle_position"] = subtitle_position_resolved
    metadata["subtitle_layout_analysis"] = subtitle_layout
    metadata["correction_dictionary"] = str(correction_dictionary) if correction_dictionary else "built-in"
    metadata["crop_mode"] = crop_mode
    metadata["keep_render_intermediates"] = keep_render_intermediates
    metadata["source_segments"] = [segment.to_dict() for segment in source_segments]
    metadata["framing_plan"] = [segment.to_dict() for segment in framing_plan]
    write_json(metadata_path, metadata)

    result = {
        "id": selection.id,
        "candidate_id": selection.candidate_id,
        "title": selection.title,
        "hook": selection.hook,
        "start": format_hms(selection.start),
        "end": format_hms(selection.end),
        "duration": round(duration, 3),
        "source_segments": [segment.to_dict() for segment in source_segments],
        "subtitle_cues": len(display_cues),
        "video": str(output_video),
        "content_video": str(content_video) if keep_render_intermediates or content_video == output_video else None,
        "subtitles": str(srt_path),
        "ass_subtitles": str(ass_path),
        "metadata": str(metadata_path),
        "caption": str(caption_path),
        "crop_mode": crop_mode,
        "crop_hint": framing_plan[0].crop_hint.reason if len(framing_plan) == 1 else "per_scene",
        "crop_confidence": round(
            sum(segment.crop_hint.confidence for segment in framing_plan) / max(1, len(framing_plan)),
            3,
        ),
        "framing_segments": len(framing_plan),
        "subtitle_correction": subtitle_correction,
        "subtitle_position": subtitle_position_resolved,
        "subtitle_layout_analysis": subtitle_layout,
        "status": "ok",
        "warnings": [],
        "intermediates_kept": keep_render_intermediates,
    }

    if burn_subtitles and not display_cues:
        result["status"] = "error"
        result["warnings"].append("no_subtitles_for_selected_segments")
        return result

    if len(framing_plan) > 1:
        ok, warnings, log = _render_scene_aware_content(
            source_video=source_video,
            framing_plan=framing_plan,
            reel_dir=reel_dir,
            content_video=content_video,
            burn_subtitles=burn_subtitles,
            fps=fps,
            crf=crf,
            preset=preset,
            allow_subtitle_fallback=allow_subtitle_fallback,
        )
        result["warnings"].extend(warnings)
        if not ok:
            result["status"] = "error"
            (reel_dir / "ffmpeg.error.txt").write_text(log, encoding="utf-8")
            return result
    else:
        crop_hint = framing_plan[0].crop_hint

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
                *_content_encode_args(fps=fps, crf=crf, preset=preset),
                str(content_video.name),
            ]

        completed = run_command(build_cmd(burn_subtitles), cwd=reel_dir, check=False)
        if completed.returncode != 0 and burn_subtitles:
            result["warnings"].append("subtitle_burn_failed")
            if allow_subtitle_fallback:
                result["warnings"].append("subtitle_fallback_without_burn")
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
            style=end_card_style,
            comment_text=end_card_comment_text,
        )
        if ok_card:
            ok_concat = _concat_videos(reel_dir=reel_dir, parts=[content_video, end_card_video], output_video=output_video)
            if not ok_concat:
                result["warnings"].append("end_card_concat_failed_content_only")
                if content_video != output_video:
                    shutil.copyfile(content_video, output_video)
        else:
            result["warnings"].append("end_card_render_failed_content_only")
            if content_video != output_video:
                shutil.copyfile(content_video, output_video)

    if not output_video.exists() or output_video.stat().st_size == 0:
        result["status"] = "error"
        result["warnings"].append("output_video_missing")
    if result["status"] == "ok":
        _cleanup_render_artifacts(
            reel_dir=reel_dir,
            output_video=output_video,
            content_video=content_video,
            end_card_video=end_card_video,
            keep_intermediates=keep_render_intermediates,
        )
    return result


def render_reels(
    *,
    source_video: Path,
    selections: list[ReelSelection],
    all_cues: list[SubtitleCue],
    output_dir: Path,
    burn_subtitles: bool = True,
    subtitle_font_size: int = 72,
    subtitle_margin_v: int = 150,
    subtitle_wrap_width: int = 30,
    subtitle_max_lines: int = 2,
    subtitle_position: str = "auto",
    subtitle_correction: str = "basic",
    correction_dictionary: Path | None = None,
    subtitle_correction_client: OllamaClient | None = None,
    force_subtitle_correction: bool = False,
    crop_mode: str = "smart",
    scenes: list[Scene] | None = None,
    fps: int = 25,
    end_card_seconds: float = 1.5,
    end_card_style: str = "short",
    end_card_comment_text: str = "",
    episode_title: str = "",
    youtube_cta: str = "Voir sur YouTube",
    youtube_url: str = "",
    crf: int = 20,
    preset: str = "medium",
    allow_subtitle_fallback: bool = False,
    keep_render_intermediates: bool = False,
    progress_callback: Callable[[int, int, str], None] | None = None,
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
                subtitle_wrap_width=subtitle_wrap_width,
                subtitle_max_lines=subtitle_max_lines,
                subtitle_position=subtitle_position,
                subtitle_correction=subtitle_correction,
                correction_dictionary=correction_dictionary,
                subtitle_correction_client=subtitle_correction_client,
                force_subtitle_correction=force_subtitle_correction,
                crop_mode=crop_mode,
                scenes=scenes,
                fps=fps,
                end_card_seconds=end_card_seconds,
                end_card_style=end_card_style,
                end_card_comment_text=end_card_comment_text,
                episode_title=episode_title,
                youtube_cta=youtube_cta,
                youtube_url=youtube_url,
                crf=crf,
                preset=preset,
                allow_subtitle_fallback=allow_subtitle_fallback,
                keep_render_intermediates=keep_render_intermediates,
            )
        )
        if progress_callback:
            progress_callback(len(results), len(selections), f"Rendu {selection.id}")
    write_json(output_dir / "render_report.json", results)
    return results
