from reelmaker.subtitles import parse_srt
from reelmaker.timecode import format_srt_time, parse_timecode


def test_parse_timecode():
    assert parse_timecode("00:01:02,500") == 62.5
    assert parse_timecode("01:02.500") == 62.5
    assert format_srt_time(62.5) == "00:01:02,500"


def test_parse_srt():
    raw = """1
00:00:01,000 --> 00:00:03,000
Bonjour <b>Orbe</b>

2
00:00:04,000 --> 00:00:06,000
Le pont commence ici.
"""
    cues = parse_srt(raw)
    assert len(cues) == 2
    assert cues[0].text == "Bonjour Orbe"
    assert cues[1].start == 4.0

from reelmaker.models import SubtitleCue
from reelmaker.subtitles import cues_for_segment


def test_cues_for_segment_drops_long_overlapping_caption():
    cues = [
        SubtitleCue(1, 0, 20, "Long caption staying forever"),
        SubtitleCue(2, 1, 3, "Short one"),
        SubtitleCue(3, 4, 6, "Short two"),
        SubtitleCue(4, 7, 9, "Short three"),
    ]

    local = cues_for_segment(cues, 0, 20)

    assert [c.text for c in local] == ["Short one", "Short two", "Short three"]
