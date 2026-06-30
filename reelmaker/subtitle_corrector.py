from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .models import ReelSelection, SubtitleCue
from .ollama_client import OllamaClient, parse_json_loose
from .utils import read_json, write_json

_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_MULTI_PUNCT_RE = re.compile(r"([!?.,;:]){3,}")
_WS_RE = re.compile(r"\s+")



def subtitle_response_schema(*, max_items: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "subtitles": {
                "type": "array",
                "minItems": 1,
                "maxItems": max(1, max_items),
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "minimum": 1},
                        "text": {"type": "string"},
                    },
                    "required": ["index", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["subtitles"],
        "additionalProperties": False,
    }


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
Tu corriges des sous-titres francais issus d'une reconnaissance vocale automatique.

Contexte video:
- Episode: {episode_title or 'non precise'}
- Reel: {selection.title}
- Accroche: {selection.hook}
- Sujet probable: {selection.reason}

Objectif:
- corriger les erreurs probables de reconnaissance vocale;
- restaurer accents, apostrophes, accords et ponctuation;
- conserver le vocabulaire technique et les noms propres lorsqu'ils sont plausibles;
- rendre chaque sous-titre grammaticalement correct sans reecrire le propos.

Regles strictes:
- Ne change PAS le sens.
- N'ajoute PAS d'information absente.
- Ne resume PAS et ne supprime PAS de mots utiles.
- Conserve le style oral et les hesitations utiles.
- Garde exactement le meme nombre d'items et les memes index.
- Utilise les items voisins comme contexte pour corriger une phrase coupee entre plusieurs sous-titres.
- Si un mot reste incertain, conserve la transcription originale.
- Reponds uniquement avec un objet JSON valide.

Format attendu:
{{
  "subtitles": [
    {{"index": 1, "text": "Texte corrige"}}
  ]
}}

Sous-titres JSON:
{json.dumps(items, ensure_ascii=False)}
"""


def _correction_fingerprint(cues: list[SubtitleCue], *, selection: ReelSelection, episode_title: str, model: str) -> str:
    payload = {
        "cues": [{"index": c.index, "start": c.start, "end": c.end, "text": c.text} for c in cues],
        "selection": selection.to_dict(),
        "episode_title": episode_title,
        "model": model,
        "schema": 2,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
    fingerprint = _correction_fingerprint(
        cues,
        selection=selection,
        episode_title=episode_title,
        model=str(getattr(client, "model", "unknown")),
    )
    if cache_path.exists() and not force:
        try:
            raw = read_json(cache_path)
            if isinstance(raw, dict) and raw.get("fingerprint") == fingerprint:
                items = raw.get("subtitles") or []
                by_index = {
                    int(item.get("index")): str(item.get("text") or "")
                    for item in items
                    if isinstance(item, dict)
                }
                if by_index:
                    return [SubtitleCue(c.index, c.start, c.end, by_index.get(c.index, c.text)) for c in cues]
        except Exception:
            pass

    prompt = _build_ollama_prompt(selection=selection, cues=cues, episode_title=episode_title)
    raw_text = client.generate(
        prompt,
        json_schema=subtitle_response_schema(max_items=len(cues)),
    )
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
    write_json(
        cache_path,
        {
            "fingerprint": fingerprint,
            "model": str(getattr(client, "model", "unknown")),
            "subtitles": [{"index": c.index, "text": c.text} for c in corrected],
        },
    )
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
