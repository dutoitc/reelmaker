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
