from __future__ import annotations

import json
import math
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .models import ReelSelection


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    sample_rate: int
    audio_channels: int

    @property
    def has_audio(self) -> bool:
        return self.audio_channels > 0


def _parse_fraction(value: str | None, default: float = 25.0) -> float:
    if not value:
        return default
    try:
        fraction = Fraction(value)
        if fraction.denominator == 0:
            return default
        result = float(fraction)
        return result if result > 0 else default
    except (ValueError, ZeroDivisionError):
        return default


def probe_media_info(path: Path) -> MediaInfo:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe failed for DaVinci XML export: {completed.stderr or completed.stdout}")

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe returned invalid JSON for DaVinci XML export.") from exc

    streams = payload.get("streams") if isinstance(payload, dict) else None
    streams = streams if isinstance(streams, list) else []
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), {})
    format_data = payload.get("format") if isinstance(payload, dict) else {}
    format_data = format_data if isinstance(format_data, dict) else {}

    duration_values = [
        format_data.get("duration"),
        video_stream.get("duration"),
        audio_stream.get("duration"),
    ]
    duration = 0.0
    for value in duration_values:
        try:
            duration = max(duration, float(value or 0.0))
        except (TypeError, ValueError):
            continue

    fps = _parse_fraction(
        str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "25/1")
    )
    return MediaInfo(
        duration=max(0.0, duration),
        width=max(1, int(video_stream.get("width") or 1920)),
        height=max(1, int(video_stream.get("height") or 1080)),
        fps=fps,
        sample_rate=max(1, int(audio_stream.get("sample_rate") or 48000)),
        audio_channels=max(0, int(audio_stream.get("channels") or 0)),
    )


def _rate_values(fps: float) -> tuple[int, bool]:
    known_ntsc = (
        (23.976, 24),
        (29.97, 30),
        (47.952, 48),
        (59.94, 60),
    )
    for actual, timebase in known_ntsc:
        if abs(fps - actual) < 0.02:
            return timebase, True
    return max(1, int(round(fps))), False


def _add_rate(parent: ET.Element, fps: float) -> None:
    timebase, ntsc = _rate_values(fps)
    rate = ET.SubElement(parent, "rate")
    ET.SubElement(rate, "timebase").text = str(timebase)
    ET.SubElement(rate, "ntsc").text = "TRUE" if ntsc else "FALSE"


def _frames(seconds: float, fps: float, *, minimum: int = 0) -> int:
    return max(minimum, int(round(max(0.0, seconds) * fps)))


def _safe_name(selection: ReelSelection) -> str:
    title = " ".join(selection.title.split()).strip()
    return f"{selection.id} - {title}" if title else selection.id


def _add_file_definition(
    clipitem: ET.Element,
    *,
    file_id: str,
    source_video: Path,
    media_info: MediaInfo,
) -> None:
    file_element = ET.SubElement(clipitem, "file", id=file_id)
    ET.SubElement(file_element, "name").text = source_video.name
    ET.SubElement(file_element, "pathurl").text = source_video.resolve().as_uri()
    _add_rate(file_element, media_info.fps)
    ET.SubElement(file_element, "duration").text = str(_frames(media_info.duration, media_info.fps, minimum=1))

    media = ET.SubElement(file_element, "media")
    video = ET.SubElement(media, "video")
    sample = ET.SubElement(video, "samplecharacteristics")
    _add_rate(sample, media_info.fps)
    ET.SubElement(sample, "width").text = str(media_info.width)
    ET.SubElement(sample, "height").text = str(media_info.height)
    ET.SubElement(sample, "anamorphic").text = "FALSE"
    ET.SubElement(sample, "pixelaspectratio").text = "square"
    ET.SubElement(sample, "fielddominance").text = "none"

    if media_info.has_audio:
        audio = ET.SubElement(media, "audio")
        ET.SubElement(audio, "channelcount").text = str(media_info.audio_channels)


def _add_clipitem(
    track: ET.Element,
    *,
    clip_id: str,
    file_id: str,
    source_video: Path,
    media_info: MediaInfo,
    source_start: float,
    source_end: float,
    timeline_start: int,
    timeline_end: int,
    mediatype: str,
    include_file: bool,
) -> ET.Element:
    clipitem = ET.SubElement(track, "clipitem", id=clip_id)
    ET.SubElement(clipitem, "name").text = source_video.name
    ET.SubElement(clipitem, "enabled").text = "TRUE"
    ET.SubElement(clipitem, "duration").text = str(_frames(media_info.duration, media_info.fps, minimum=1))
    _add_rate(clipitem, media_info.fps)
    ET.SubElement(clipitem, "start").text = str(timeline_start)
    ET.SubElement(clipitem, "end").text = str(timeline_end)
    source_in = _frames(source_start, media_info.fps)
    source_frame_count = _frames(source_end - source_start, media_info.fps, minimum=1)
    source_out = source_in + source_frame_count
    ET.SubElement(clipitem, "in").text = str(source_in)
    ET.SubElement(clipitem, "out").text = str(source_out)

    if include_file:
        _add_file_definition(
            clipitem,
            file_id=file_id,
            source_video=source_video,
            media_info=media_info,
        )
    else:
        ET.SubElement(clipitem, "file", id=file_id)

    source_track = ET.SubElement(clipitem, "sourcetrack")
    ET.SubElement(source_track, "mediatype").text = mediatype
    ET.SubElement(source_track, "trackindex").text = "1"
    return clipitem


def _add_link(clipitem: ET.Element, *, clip_ref: str, mediatype: str, group_index: int | None = None) -> None:
    link = ET.SubElement(clipitem, "link")
    ET.SubElement(link, "linkclipref").text = clip_ref
    ET.SubElement(link, "mediatype").text = mediatype
    ET.SubElement(link, "trackindex").text = "1"
    ET.SubElement(link, "clipindex").text = "1"
    if group_index is not None:
        ET.SubElement(link, "groupindex").text = str(group_index)


def build_davinci_xml(
    *,
    source_video: Path,
    selection: ReelSelection,
    media_info: MediaInfo,
    timeline_fps: float = 25.0,
    timeline_width: int = 1080,
    timeline_height: int = 1920,
) -> str:
    source_segments = selection.source_segments
    if not source_segments:
        raise ValueError(f"Selection {selection.id} contains no valid source segment.")

    xmeml = ET.Element("xmeml", version="5")
    sequence = ET.SubElement(xmeml, "sequence", id=f"sequence-{selection.id}")
    ET.SubElement(sequence, "name").text = _safe_name(selection)
    _add_rate(sequence, timeline_fps)

    segment_frame_counts = [
        _frames(segment.duration, timeline_fps, minimum=1)
        for segment in source_segments
    ]
    sequence_duration = sum(segment_frame_counts)
    ET.SubElement(sequence, "duration").text = str(sequence_duration)

    timecode = ET.SubElement(sequence, "timecode")
    _add_rate(timecode, timeline_fps)
    ET.SubElement(timecode, "string").text = "00:00:00:00"
    ET.SubElement(timecode, "frame").text = "0"
    ET.SubElement(timecode, "displayformat").text = "NDF"

    marker = ET.SubElement(sequence, "marker")
    ET.SubElement(marker, "name").text = selection.hook or selection.title or selection.id
    ET.SubElement(marker, "comment").text = selection.reason or selection.transcript_excerpt
    ET.SubElement(marker, "in").text = "0"
    ET.SubElement(marker, "out").text = "-1"

    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")
    video_format = ET.SubElement(video, "format")
    sequence_sample = ET.SubElement(video_format, "samplecharacteristics")
    _add_rate(sequence_sample, timeline_fps)
    ET.SubElement(sequence_sample, "width").text = str(timeline_width)
    ET.SubElement(sequence_sample, "height").text = str(timeline_height)
    ET.SubElement(sequence_sample, "anamorphic").text = "FALSE"
    ET.SubElement(sequence_sample, "pixelaspectratio").text = "square"
    ET.SubElement(sequence_sample, "fielddominance").text = "none"
    video_track = ET.SubElement(video, "track")

    audio_track: ET.Element | None = None
    if media_info.has_audio:
        audio = ET.SubElement(media, "audio")
        ET.SubElement(audio, "numOutputChannels").text = str(media_info.audio_channels)
        audio_format = ET.SubElement(audio, "format")
        audio_sample = ET.SubElement(audio_format, "samplecharacteristics")
        ET.SubElement(audio_sample, "depth").text = "16"
        ET.SubElement(audio_sample, "samplerate").text = str(media_info.sample_rate)
        audio_track = ET.SubElement(audio, "track")

    timeline_cursor = 0
    file_id = f"file-{selection.id}"
    for index, (segment, frame_count) in enumerate(zip(source_segments, segment_frame_counts, strict=True), start=1):
        timeline_end = timeline_cursor + frame_count
        video_id = f"video-{selection.id}-{index}"
        audio_id = f"audio-{selection.id}-{index}"
        video_item = _add_clipitem(
            video_track,
            clip_id=video_id,
            file_id=file_id,
            source_video=source_video,
            media_info=media_info,
            source_start=segment.start,
            source_end=segment.end,
            timeline_start=timeline_cursor,
            timeline_end=timeline_end,
            mediatype="video",
            include_file=index == 1,
        )
        if audio_track is not None:
            audio_item = _add_clipitem(
                audio_track,
                clip_id=audio_id,
                file_id=file_id,
                source_video=source_video,
                media_info=media_info,
                source_start=segment.start,
                source_end=segment.end,
                timeline_start=timeline_cursor,
                timeline_end=timeline_end,
                mediatype="audio",
                include_file=False,
            )
            _add_link(video_item, clip_ref=video_id, mediatype="video")
            _add_link(video_item, clip_ref=audio_id, mediatype="audio", group_index=1)
            _add_link(audio_item, clip_ref=video_id, mediatype="video")
            _add_link(audio_item, clip_ref=audio_id, mediatype="audio", group_index=1)
        timeline_cursor = timeline_end

    ET.indent(xmeml, space="  ")
    xml_body = ET.tostring(xmeml, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + xml_body + "\n"


def export_davinci_xmls(
    *,
    source_video: Path,
    selections: list[ReelSelection],
    output_dir: Path,
    timeline_fps: float = 25.0,
) -> list[Path]:
    media_info = probe_media_info(source_video)
    output_paths: list[Path] = []
    for selection in selections:
        reel_dir = output_dir / selection.id
        reel_dir.mkdir(parents=True, exist_ok=True)
        output_path = reel_dir / f"{selection.id}.xml"
        output_path.write_text(
            build_davinci_xml(
                source_video=source_video,
                selection=selection,
                media_info=media_info,
                timeline_fps=timeline_fps,
            ),
            encoding="utf-8",
            newline="\n",
        )
        output_paths.append(output_path)
    return output_paths
