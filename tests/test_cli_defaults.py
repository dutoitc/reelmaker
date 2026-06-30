from reelmaker.cli import build_parser


def test_all_command_uses_quality_oriented_defaults():
    args = build_parser().parse_args(["all", "--source-video", "reportage.mp4"])

    assert args.composition_mode == "hybrid"
    assert args.subtitle_correction == "ollama"
    assert args.allow_subtitle_fallback is False
