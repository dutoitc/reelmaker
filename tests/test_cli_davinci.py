from reelmaker.cli import build_parser


def test_xml_command_and_davinci_flag_are_available(tmp_path):
    parser = build_parser()
    args = parser.parse_args([
        "xml",
        "--source-video", str(tmp_path / "source.mp4"),
        "--output-dir", str(tmp_path / "output"),
    ])
    assert args.command == "xml"
    assert args.fps == 25

    all_args = parser.parse_args([
        "all",
        "--source-video", str(tmp_path / "source.mp4"),
        "--davinci-xml",
    ])
    assert all_args.davinci_xml is True
