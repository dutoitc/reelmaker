from __future__ import annotations

import re
from pathlib import Path

from .models import ReelSelection, SubtitleCue
from .ollama_client import OllamaClient, parse_json_loose
from .utils import read_json, write_json

_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_MULTI_PUNCT_RE = re.compile(r"([!?.,;:]){3,}")
_WS_RE = re.compile(r"\s+")

_COMMON_FIXES = {
    "ecolosons": "eclosions",
    "eclosons": "eclosions",
    "eclosion": "eclosion",
    "nichoire": "nichoir",
    "hulote": "hulotte",
    "hulotes": "hulottes",
    "chouette hulote": "chouette hulotte",
    "chouettes hulotes": "chouettes hulottes",
    "bertran": "Bertrand",
    "stephane": "Stephane",
}


def _preserve_case_replace(text: str, wrong: str, right: str) -> str:
    pattern = re.compile(rf"\b{re.escape(wrong)}\b", flags=re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        found = match.group(0)
        if found.isupper():
            return right.upper()
        if found[:1].isupper():
            return right[:1].upper() + right[1:]
        return right

    return pattern.sub(repl, text)


def correct_text_basic(text: str) -> str:
    """Lightweight subtitle cleanup without changing meaning.

    This is intentionally conservative: it fixes spacing, duplicated punctuation,
    common French typography, and a few domain words that often appear in the
    CAPStv/Xplore kind of transcripts.
    """
    text = _WS_RE.sub(" ", text or "").strip()
    text = text.replace(" ,", ",").replace(" .", ".")
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = re.sub(r"\s+(['’])\s+", r"\1", text)
    text = _MULTI_PUNCT_RE.sub(lambda m: m.group(1), text)
    for wrong, right in _COMMON_FIXES.items():
        text = _preserve_case_replace(text, wrong, right)
    if text:
        text = text[0].upper() + text[1:]
    return text


def correct_cues_basic(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    return [SubtitleCue(index=c.index, start=c.start, end=c.end, text=correct_text_basic(c.text)) for c in cues]


def _build_ollama_prompt(*, selection: ReelSelection, cues: list[SubtitleCue], episode_title: str) -> str:
    items = [{"index": c.index, "text": c.text} for c in cues]
    return f"""/no_think
Tu corriges des sous-titres français extraits automatiquement de YouTube.

Objectif: corriger uniquement les fautes probables de transcription, grammaire légère et ponctuation.

Contexte vidéo:
- Episode: {episode_title or 'non precise'}
- Extrait: {selection.title}
- Accroche: {selection.hook}

Règles strictes:
- Ne change PAS le sens.
- N'ajoute PAS de nouvelles informations.
- Ne transforme PAS le style oral en texte littéraire.
- Garde les phrases courtes, lisibles sur smartphone.
- Conserve le même nombre d'items et les mêmes index.
- Si le texte est déjà correct, garde-le presque identique.
- Réponds uniquement avec un JSON valide.

Format attendu:
{{
  "subtitles": [
    {{"index": 1, "text": "Texte corrige"}}
  ]
}}

Sous-titres JSON:
{items}
"""


def correct_cues_with_ollama(
    cues: list[SubtitleCue],
    *,
    selection: ReelSelection,
    episode_title: str,
    client: OllamaClient,
    cache_path: Path,
    force: bool = False,
) -> list[SubtitleCue]:
    if not cues:
        return []
    if cache_path.exists() and not force:
        try:
            raw = read_json(cache_path)
            if isinstance(raw, list) and len(raw) == len(cues):
                by_index = {int(item.get("index")): str(item.get("text") or "") for item in raw if isinstance(item, dict)}
                if by_index:
                    return [SubtitleCue(c.index, c.start, c.end, by_index.get(c.index, c.text)) for c in cues]
        except Exception:
            pass

    prompt = _build_ollama_prompt(selection=selection, cues=cues, episode_title=episode_title)
    raw_text = client.generate(prompt)
    raw_path = cache_path.with_suffix(".raw.txt")
    raw_path.write_text(raw_text, encoding="utf-8")
    payload = parse_json_loose(raw_text)
    items = payload.get("subtitles", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        raise ValueError("Subtitle correction response does not contain a subtitles list")

    corrected = correct_cues_basic(cues)
    by_index = {
        int(item.get("index")): correct_text_basic(str(item.get("text") or ""))
        for item in items
        if isinstance(item, dict) and item.get("index") is not None
    }
    if by_index:
        corrected = [
            SubtitleCue(c.index, c.start, c.end, by_index.get(c.index, c.text))
            for c in corrected
        ]
    write_json(cache_path, [{"index": c.index, "text": c.text} for c in corrected])
    return corrected


def maybe_correct_cues(
    cues: list[SubtitleCue],
    *,
    mode: str,
    selection: ReelSelection,
    episode_title: str,
    client: OllamaClient | None,
    cache_path: Path,
    force: bool = False,
) -> list[SubtitleCue]:
    if mode == "off":
        return cues
    if mode == "basic":
        return correct_cues_basic(cues)
    if mode == "ollama":
        if client is None:
            raise ValueError("Ollama subtitle correction requires an OllamaClient")
        try:
            return correct_cues_with_ollama(
                cues,
                selection=selection,
                episode_title=episode_title,
                client=client,
                cache_path=cache_path,
                force=force,
            )
        except Exception as exc:
            cache_path.with_suffix(".error.txt").write_text(str(exc), encoding="utf-8")
            return correct_cues_basic(cues)
    raise ValueError(f"Unknown subtitle correction mode: {mode}")
