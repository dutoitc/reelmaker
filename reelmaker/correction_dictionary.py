from __future__ import annotations

import json
import re
from importlib.resources import files
from pathlib import Path
from typing import Any


DictionaryData = dict[str, dict[str, str]]


def _read_dictionary(path: Path) -> DictionaryData:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Correction dictionary must be an object: {path}")
    result: DictionaryData = {"replacements": {}, "proper_nouns": {}}
    for section in result:
        values = raw.get(section, {})
        if isinstance(values, dict):
            result[section] = {
                str(key).strip(): str(value).strip()
                for key, value in values.items()
                if str(key).strip() and str(value).strip()
            }
    return result


def load_correction_dictionary(extra_path: Path | None = None) -> DictionaryData:
    built_in_path = Path(str(files("reelmaker").joinpath("data/corrections_fr.json")))
    data = _read_dictionary(built_in_path)
    if extra_path is None:
        return data
    extra = _read_dictionary(extra_path)
    for section in data:
        data[section].update(extra.get(section, {}))
    return data


def dictionary_fingerprint_payload(extra_path: Path | None = None) -> dict[str, Any]:
    data = load_correction_dictionary(extra_path)
    return {
        "dictionary": data,
        "extra_path": str(extra_path.resolve()) if extra_path else None,
    }


def _replace_word_or_phrase(text: str, wrong: str, right: str, *, preserve_case: bool) -> str:
    pattern = re.compile(rf"(?<!\w){re.escape(wrong)}(?!\w)", flags=re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        if not preserve_case:
            return right
        found = match.group(0)
        if found.isupper():
            return right.upper()
        if found[:1].isupper():
            return right[:1].upper() + right[1:]
        return right

    return pattern.sub(repl, text)


def apply_correction_dictionary(text: str, extra_path: Path | None = None) -> str:
    data = load_correction_dictionary(extra_path)
    for wrong, right in sorted(data["replacements"].items(), key=lambda item: len(item[0]), reverse=True):
        text = _replace_word_or_phrase(text, wrong, right, preserve_case=True)
    for wrong, right in sorted(data["proper_nouns"].items(), key=lambda item: len(item[0]), reverse=True):
        text = _replace_word_or_phrase(text, wrong, right, preserve_case=False)
    return text
