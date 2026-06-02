from __future__ import annotations

import os
import sys
import unicodedata
from typing import Any


def configure_console() -> None:
    """Make console output safer on Windows terminals.

    The JSON files are always written as UTF-8. For interactive display on
    Windows/Git Bash, model-generated accents can still be mojibaked depending
    on the terminal codepage. By default we keep logs readable by printing
    ASCII-safe text. Set REELMAKER_UNICODE_CONSOLE=1 to keep accents in the
    console.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def console_text(value: Any) -> str:
    text = str(value)
    if os.environ.get("REELMAKER_UNICODE_CONSOLE") == "1":
        return text
    if os.name != "nt":
        return text
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text


def cprint(value: Any = "") -> None:
    print(console_text(value))
