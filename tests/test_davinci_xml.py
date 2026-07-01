from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from reelmaker.davinci_xml import MediaInfo, build_davinci_xml, export_davinci_xmls
from reelmaker.models import ReelSegment, ReelSelection


def _selection(*, composite: bool = False) -> ReelSelection:
    segments = [ReelSegment(10.0, 14.0), ReelSegment(30.0, 33.0)] if composite else []
    return ReelSelection(
        id="R01",
        candidate_id="C001",
        rank=1,
        start=10.0,
        end=14.0,
        title="Une idée forte",
        hook="Le détail qui change tout",
        reason="Deux passages complémentaires.",
        transcript_excerpt="Extrait test",
        segments=segments,
    )


def _media_info() -> MediaInfo:
    return MediaInfo(
        duration=120.0,
        width=1920,
        height=1080,
        fps=25.0,
        sample_rate=48000,
        audio_channels=2,
    )


def _root(xml_text: str) -> ET.Element:
    without_doctype = xml_text.replace("<!DOCTYPE xmeml>\n", "")
    return ET.fromstring(without_doctype)


def test_build_davinci_xml_uses_vertical_timeline_and_original_source(tmp_path: Path):
    source = tmp_path / "vidéo source.mp4"
    source.write_bytes(b"video")

    root = _root(
        build_davinci_xml(
            source_video=source,
            selection=_selection(),
            media_info=_media_info(),
            timeline_fps=25.0,
        )
    )

    assert root.tag == "xmeml"
    assert root.findtext("./sequence/name") == "R01 - Une idée forte"
    assert root.findtext("./sequence/media/video/format/samplecharacteristics/width") == "1080"
    assert root.findtext("./sequence/media/video/format/samplecharacteristics/height") == "1920"
    assert root.findtext(".//pathurl") == source.resolve().as_uri()
    assert root.findtext(".//clipitem/in") == "250"
    assert root.findtext(".//clipitem/out") == "350"
    assert root.find("./sequence/media/audio/track/clipitem") is not None


def test_composite_selection_creates_one_source_clip_per_segment(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    root = _root(
        build_davinci_xml(
            source_video=source,
            selection=_selection(composite=True),
            media_info=_media_info(),
            timeline_fps=25.0,
        )
    )

    video_items = root.findall("./sequence/media/video/track/clipitem")
    audio_items = root.findall("./sequence/media/audio/track/clipitem")
    assert len(video_items) == 2
    assert len(audio_items) == 2
    assert [item.findtext("start") for item in video_items] == ["0", "100"]
    assert [item.findtext("end") for item in video_items] == ["100", "175"]
    assert [item.findtext("in") for item in video_items] == ["250", "750"]
    assert len(video_items[0].findall("link")) == 2


def test_export_davinci_xmls_places_file_in_each_reel_folder(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr("reelmaker.davinci_xml.probe_media_info", lambda _path: _media_info())

    paths = export_davinci_xmls(
        source_video=source,
        selections=[_selection()],
        output_dir=tmp_path / "reels",
        timeline_fps=25.0,
    )

    assert paths == [tmp_path / "reels" / "R01" / "R01.xml"]
    assert paths[0].is_file()
    assert "<!DOCTYPE xmeml>" in paths[0].read_text(encoding="utf-8")
