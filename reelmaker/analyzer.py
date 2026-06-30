from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .console import cprint
from .models import ReelCandidate, ReelSegment, ReelSelection, SubtitleCue, TranscriptChunk
from .ollama_client import OllamaClient, parse_json_loose
from .timecode import format_hms, parse_timecode
from .utils import read_json, write_json




def candidate_response_schema(*, max_candidates: int, allow_montage: bool = True) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "start_time": {"type": "string"},
        "end_time": {"type": "string"},
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "reason": {"type": "string"},
        "score": {"type": "number", "minimum": 0, "maximum": 10},
        "transcript_excerpt": {"type": "string"},
    }
    if allow_montage:
        properties["segments"] = {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                },
                "required": ["start_time", "end_time"],
                "additionalProperties": False,
            },
        }

    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "minItems": 1,
                "maxItems": max(1, max_candidates),
                "items": {
                    "type": "object",
                    "properties": properties,
                    "required": [
                        "start_time",
                        "end_time",
                        "title",
                        "hook",
                        "reason",
                        "score",
                        "transcript_excerpt",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    }


def ranking_response_schema(*, max_selected: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "selected": {
                "type": "array",
                "minItems": 1,
                "maxItems": max(1, max_selected),
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {"type": "string"},
                        "rank": {"type": "integer", "minimum": 1},
                        "improved_hook": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["candidate_id", "rank", "improved_hook", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["selected"],
        "additionalProperties": False,
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str) and ":" in value:
            return parse_timecode(value)
        return float(value)
    except Exception:
        return default


def _safe_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(10.0, score))


def _candidate_from_dict(data: dict[str, Any]) -> ReelCandidate:
    segments: list[ReelSegment] = []
    for item in data.get("segments") or []:
        if not isinstance(item, dict):
            continue
        start = _safe_float(item.get("start"), 0.0)
        end = _safe_float(item.get("end"), start)
        if end > start:
            segments.append(ReelSegment(start, end))
    return ReelCandidate(
        id=str(data.get("id") or "C000"),
        start=_safe_float(data.get("start"), 0.0),
        end=_safe_float(data.get("end"), 0.0),
        title=str(data.get("title") or "Extrait"),
        hook=str(data.get("hook") or ""),
        reason=str(data.get("reason") or ""),
        score=_safe_score(data.get("score")),
        transcript_excerpt=str(data.get("transcript_excerpt") or ""),
        source_chunk=data.get("source_chunk"),
        warnings=list(data.get("warnings") or []),
        boundary_method=str(data.get("boundary_method")) if data.get("boundary_method") else None,
        boundary_score=_safe_float(data.get("boundary_score"), 0.0) if data.get("boundary_score") is not None else None,
        boundary_reasons=list(data.get("boundary_reasons") or []),
        segments=segments,
    )


def build_chunk_prompt(
    chunk: TranscriptChunk,
    *,
    candidates_per_chunk: int,
    min_duration: int,
    max_duration: int,
    composition_mode: str = "hybrid",
) -> str:
    montage_rules = """
- Tu peux recomposer un reel avec 2 ou 3 passages NON CONTIGUS parlant du meme sujet.
- Pour un montage, renseigne `segments` dans l'ordre narratif, avec les timecodes exacts.
- La somme des segments doit respecter la duree cible.
- Un montage doit apporter une vraie progression: accroche, explication, conclusion.
- Propose au moins un montage si le transcript contient des passages complementaires.
""" if composition_mode == "hybrid" else "- Propose uniquement un passage continu; n\'utilise pas `segments`.\n"
    return f"""/no_think
Tu es un monteur editorial specialise en Instagram Reels, TikTok et YouTube Shorts.

Objectif: trouver des mini-histoires autonomes, marquantes et partageables a partir d'une video longue.

Un candidat n'est valable que s'il possede un angle editorial precis. Il doit contenir au moins un element fort:
- fait surprenant ou contre-intuitif;
- chiffre, date, comparaison ou consequence concrete;
- reponse claire a une question que le public peut se poser;
- transformation, probleme puis solution, ou tension puis conclusion;
- detail local, humain ou visuel que l'on retient apres le visionnage.

Regles strictes:
- Utilise UNIQUEMENT le transcript fourni.
- N'invente aucun fait, lieu, nom, date ou conclusion.
- Les timecodes doivent venir du transcript.
- Le reel doit etre comprehensible sans contexte externe.
- Les 3 premieres secondes doivent contenir une information, une surprise ou une question forte.
- Le reel doit se terminer sur une phrase complete ou une conclusion naturelle.
- Duree totale cible: {min_duration} a {max_duration} secondes, idealement 20 a 35 secondes.
- REJETTE les extraits simplement informatifs, generiques ou sans conclusion memorable.
- REJETTE les extraits qui ne sont qu'un morceau arbitraire de la video.
- Evite les introductions vagues, repetitions, salutations et transitions techniques.
- Ne propose pas deux reels quasi identiques.
- Le hook doit annoncer la promesse reelle du contenu, sans inventer ni exagérer.
- Privilegie la densite: chaque phrase doit faire avancer l'idee.
{montage_rules}- Reponds uniquement avec UN objet JSON valide, sans markdown ni commentaire.
- Limite les champs texte a des phrases courtes.

Criteres de score /10:
- Force de l'idee et caractere memorable: 30%
- Specificite (faits, consequences, exemples): 20%
- Accroche des 3 premieres secondes: 20%
- Progression narrative et autonomie: 20%
- Fin naturelle et satisfaisante: 10%

N'attribue pas plus de 7/10 a un extrait generique ou sans payoff clair.

Format JSON attendu pour un passage continu:
{{
  "candidates": [
    {{
      "start_time": "00:00:00,000",
      "end_time": "00:00:25,000",
      "title": "Titre court",
      "hook": "Phrase d'accroche courte",
      "reason": "Pourquoi ce reel peut marcher",
      "score": 8.0,
      "transcript_excerpt": "Texte exact ou quasi exact"
    }}
  ]
}}

Pour un montage, ajoute par exemple:
"segments": [
  {{"start_time": "00:00:10,000", "end_time": "00:00:18,000"}},
  {{"start_time": "00:02:20,000", "end_time": "00:02:34,000"}}
]

Nombre maximum de candidats pour ce bloc: {candidates_per_chunk}

Transcript bloc {chunk.index}, de {format_hms(chunk.start)} a {format_hms(chunk.end)}:
{chunk.text}
"""


def _parse_segments(item: dict[str, Any], *, chunk: TranscriptChunk) -> list[ReelSegment]:
    segments: list[ReelSegment] = []
    for raw_segment in item.get("segments") or []:
        if not isinstance(raw_segment, dict):
            continue
        start = _safe_float(raw_segment.get("start_time"), chunk.start)
        end = _safe_float(raw_segment.get("end_time"), start)
        if end <= start:
            continue
        if start < chunk.start - 2 or end > chunk.end + 2:
            continue
        segments.append(ReelSegment(start, end))
    return segments[:3]


def _candidates_from_payload(
    payload: Any,
    *,
    chunk: TranscriptChunk,
    start_index: int,
    min_duration: int,
    max_duration: int,
    composition_mode: str = "hybrid",
) -> list[ReelCandidate]:
    items = payload.get("candidates", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []

    candidates: list[ReelCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        segments = _parse_segments(item, chunk=chunk) if composition_mode == "hybrid" else []
        start = _safe_float(item.get("start_time"), default=chunk.start)
        end = _safe_float(item.get("end_time"), default=start)
        if segments:
            start = segments[0].start
            end = segments[-1].end
        warnings: list[str] = []
        if end <= start:
            continue
        if start < chunk.start - 2 or end > chunk.end + 2:
            warnings.append("outside_source_chunk")
        duration = sum(segment.duration for segment in segments) if segments else end - start
        if duration < min_duration:
            warnings.append("too_short")
        if duration > max_duration:
            warnings.append("too_long")
        if len(segments) > 1:
            warnings.append("composite_montage")

        candidates.append(
            ReelCandidate(
                id=f"C{start_index + len(candidates):03d}",
                start=start,
                end=end,
                title=str(item.get("title", "Extrait")).strip()[:120],
                hook=str(item.get("hook", "")).strip()[:220],
                reason=str(item.get("reason", "")).strip()[:500],
                score=_safe_score(item.get("score")),
                transcript_excerpt=str(item.get("transcript_excerpt", "")).strip()[:1600],
                source_chunk=chunk.index,
                warnings=warnings,
                segments=segments,
            )
        )
    return candidates


def _load_cached_candidates(path: Path) -> list[ReelCandidate] | None:
    if not path.exists():
        return None
    try:
        raw = read_json(path)
        if not isinstance(raw, list):
            return None
        return [_candidate_from_dict(item) for item in raw if isinstance(item, dict)]
    except Exception:
        return None


def _try_parse_existing_raw(
    raw_path: Path,
    candidates_path: Path,
    *,
    chunk: TranscriptChunk,
    start_index: int,
    min_duration: int,
    max_duration: int,
    composition_mode: str = "hybrid",
) -> list[ReelCandidate] | None:
    if not raw_path.exists():
        return None
    try:
        raw = raw_path.read_text(encoding="utf-8", errors="replace")
        payload = parse_json_loose(raw)
        candidates = _candidates_from_payload(
            payload,
            chunk=chunk,
            start_index=start_index,
            min_duration=min_duration,
            max_duration=max_duration,
            composition_mode=composition_mode,
        )
        if candidates:
            write_json(candidates_path, [c.to_dict() for c in candidates])
            return candidates
    except Exception as exc:
        candidates_path.with_suffix(".error.txt").write_text(str(exc), encoding="utf-8")
    return None


def generate_candidates(
    chunks: list[TranscriptChunk],
    client: OllamaClient,
    logs_dir: Path,
    *,
    candidates_per_chunk: int = 3,
    min_duration: int = 15,
    max_duration: int = 75,
    resume: bool = True,
    force_ollama: bool = False,
    composition_mode: str = "contiguous",
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[ReelCandidate]:
    all_candidates: list[ReelCandidate] = []

    for pos, chunk in enumerate(chunks, start=1):
        if composition_mode == "contiguous":
            raw_path = logs_dir / f"ollama_chunk_{chunk.index:03d}.impact_v2.txt"
            candidates_path = logs_dir / f"ollama_chunk_{chunk.index:03d}.impact_v2.candidates.json"
        else:
            cache_suffix = composition_mode.replace("-", "_") + ".impact_v2"
            raw_path = logs_dir / f"ollama_chunk_{chunk.index:03d}.{cache_suffix}.txt"
            candidates_path = logs_dir / f"ollama_chunk_{chunk.index:03d}.{cache_suffix}.candidates.json"

        if resume and not force_ollama:
            cached = _load_cached_candidates(candidates_path)
            if cached:
                print(
                    f"Ollama candidate analysis: chunk {pos}/{len(chunks)} "
                    f"({format_hms(chunk.start)}-{format_hms(chunk.end)}) - cache"
                )
                all_candidates.extend(cached)
                if progress_callback:
                    progress_callback(pos, len(chunks), f"Bloc {pos}/{len(chunks)} (cache)")
                continue

            parsed = _try_parse_existing_raw(
                raw_path,
                candidates_path,
                chunk=chunk,
                start_index=len(all_candidates) + 1,
                min_duration=min_duration,
                max_duration=max_duration,
                composition_mode=composition_mode,
            )
            if parsed:
                print(
                    f"Ollama candidate analysis: chunk {pos}/{len(chunks)} "
                    f"({format_hms(chunk.start)}-{format_hms(chunk.end)}) - reused raw log"
                )
                all_candidates.extend(parsed)
                if progress_callback:
                    progress_callback(pos, len(chunks), f"Bloc {pos}/{len(chunks)} (log reutilise)")
                continue

        print(
            f"Ollama candidate analysis: chunk {pos}/{len(chunks)} "
            f"({format_hms(chunk.start)}-{format_hms(chunk.end)})"
        )
        prompt = build_chunk_prompt(
            chunk,
            candidates_per_chunk=candidates_per_chunk,
            min_duration=min_duration,
            max_duration=max_duration,
            composition_mode=composition_mode,
        )
        try:
            raw = client.generate(
                prompt,
                json_schema=candidate_response_schema(
                    max_candidates=candidates_per_chunk,
                    allow_montage=composition_mode == "hybrid",
                ),
            )
        except RuntimeError as exc:
            (logs_dir / f"ollama_chunk_{chunk.index:03d}.error.txt").write_text(str(exc), encoding="utf-8")
            print(f"  skipped: {exc}")
            if progress_callback:
                progress_callback(pos, len(chunks), f"Bloc {pos}/{len(chunks)} en erreur")
            continue
        raw_path.write_text(raw, encoding="utf-8")

        try:
            payload = parse_json_loose(raw)
            candidates = _candidates_from_payload(
                payload,
                chunk=chunk,
                start_index=len(all_candidates) + 1,
                min_duration=min_duration,
                max_duration=max_duration,
                composition_mode=composition_mode,
            )
            write_json(candidates_path, [c.to_dict() for c in candidates])
            all_candidates.extend(candidates)
        except ValueError as exc:
            (logs_dir / f"ollama_chunk_{chunk.index:03d}.error.txt").write_text(str(exc), encoding="utf-8")
        finally:
            if progress_callback:
                progress_callback(pos, len(chunks), f"Bloc {pos}/{len(chunks)}")

    # Cached chunks can contain IDs produced under an older partial run.
    # Reassign them deterministically after merging to prevent duplicate IDs.
    for index, candidate in enumerate(all_candidates, start=1):
        candidate.id = f"C{index:03d}"
    return all_candidates



def generate_global_composite_candidates(
    cues: list[SubtitleCue],
    client: OllamaClient,
    logs_dir: Path,
    *,
    max_candidates: int = 3,
    min_duration: int = 18,
    max_duration: int = 60,
    resume: bool = True,
    force_ollama: bool = False,
    max_transcript_chars: int = 48000,
) -> list[ReelCandidate]:
    """Ask for cross-video montages that chunk-local analysis cannot discover."""
    if max_candidates <= 0 or not cues:
        return []
    transcript = "\n".join(
        f"[{format_hms(cue.start)}-{format_hms(cue.end)}] {cue.text}"
        for cue in cues
    )
    if len(transcript) > max_transcript_chars:
        print("Global composite analysis skipped: transcript too long for a safe local-model request")
        return []

    chunk = TranscriptChunk(
        index=0,
        start=cues[0].start,
        end=cues[-1].end,
        text=transcript,
        cue_indexes=[cue.index for cue in cues],
    )
    raw_path = logs_dir / "ollama_global_composites.impact_v2.txt"
    candidates_path = logs_dir / "ollama_global_composites.impact_v2.candidates.json"

    if resume and not force_ollama:
        cached = _load_cached_candidates(candidates_path)
        if cached:
            print(f"Global composite analysis: {len(cached)} candidates - cache")
            return cached

    prompt = f"""/no_think
Tu es le redacteur en chef d'une chaine video locale. Tu disposes du transcript COMPLET.

Construis jusqu'a {max_candidates} reels marquants en combinant 2 ou 3 passages non contigus.
Chaque montage doit former une mini-histoire plus forte qu'un extrait continu:
1. une accroche concrete ou surprenante;
2. une explication qui apporte une information nouvelle;
3. une conclusion, consequence ou payoff memorable.

Regles absolues:
- utilise uniquement les paroles et timecodes fournis;
- n'invente aucune transition, aucun fait ni conclusion;
- les passages doivent traiter exactement du meme angle;
- evite les montages qui ressemblent a une compilation aleatoire;
- termine chaque segment sur une phrase ou une pause naturelle;
- duree totale: {min_duration} a {max_duration} secondes;
- rejette les sujets generiques sans surprise, consequence ou detail concret;
- reponds uniquement avec l'objet JSON demande.

Format attendu:
{{
  "candidates": [
    {{
      "start_time": "00:00:10,000",
      "end_time": "00:03:20,000",
      "segments": [
        {{"start_time": "00:00:10,000", "end_time": "00:00:18,000"}},
        {{"start_time": "00:02:20,000", "end_time": "00:02:34,000"}}
      ],
      "title": "Titre court",
      "hook": "Promesse exacte et forte",
      "reason": "Angle, progression et payoff",
      "score": 8.5,
      "transcript_excerpt": "Resume fidele des passages choisis"
    }}
  ]
}}

Transcript complet:
{transcript}
"""
    try:
        raw = client.generate(
            prompt,
            json_schema=candidate_response_schema(max_candidates=max_candidates, allow_montage=True),
        )
    except RuntimeError as exc:
        raw_path.with_suffix(".error.txt").write_text(str(exc), encoding="utf-8")
        print(f"Global composite analysis skipped: {exc}")
        return []
    raw_path.write_text(raw, encoding="utf-8")
    try:
        payload = parse_json_loose(raw)
        candidates = _candidates_from_payload(
            payload,
            chunk=chunk,
            start_index=1,
            min_duration=min_duration,
            max_duration=max_duration,
            composition_mode="hybrid",
        )
    except Exception as exc:
        candidates_path.with_suffix(".error.txt").write_text(str(exc), encoding="utf-8")
        return []

    composites: list[ReelCandidate] = []
    for candidate in candidates:
        if not candidate.is_composite:
            continue
        if "global_composite" not in candidate.warnings:
            candidate.warnings.append("global_composite")
        composites.append(candidate)
    write_json(candidates_path, [candidate.to_dict() for candidate in composites])
    print(f"Global composite analysis: {len(composites)} candidates")
    return composites


def build_ranking_prompt(candidates: list[ReelCandidate], *, shortlist_count: int, target_count: int) -> str:
    compact = [
        {
            "id": c.id,
            "start": format_hms(c.start),
            "end": format_hms(c.end),
            "duration": round(c.duration, 1),
            "title": c.title,
            "hook": c.hook,
            "score": c.score,
            "reason": c.reason,
            "excerpt": c.transcript_excerpt[:400],
            "warnings": c.warnings,
            "boundary_method": c.boundary_method,
            "boundary_score": c.boundary_score,
        }
        for c in candidates
    ]
    return f"""/no_think
Tu es un assistant de stratégie éditoriale pour vidéos courtes.

Objectif: classer des candidats de reels issus d'une vidéo longue.

Règles strictes:
- Ne modifie pas les timecodes.
- Ne crée pas de nouveaux extraits.
- Sélectionne les meilleurs extraits déjà proposés.
- Évite les doublons thématiques.
- Vise une série finale de {target_count} reels, mais retourne une shortlist de {shortlist_count} pour validation humaine.
- Favorise les extraits autonomes, spécifiques, surprenants ou émotionnels, avec un payoff clair.
- Favorise les montages recomposes lorsqu'ils créent une vraie progression et restent naturels.
- Pénalise fortement les idées génériques, les simples bouts d'interview et les candidats sans conclusion mémorable.
- Pénalise les candidats marqués too_short, too_long, boundary_incomplete_end ou outside_source_chunk.
- Réponds uniquement avec UN objet JSON valide.
- Ne mets aucun texte avant ou après le JSON.
- Ne mets pas de markdown.

Format JSON attendu:
{{
  "selected": [
    {{
      "candidate_id": "C001",
      "rank": 1,
      "improved_hook": "Accroche améliorée sans inventer",
      "reason": "Pourquoi il est dans le top"
    }}
  ]
}}

Candidats JSON:
{json.dumps(compact, ensure_ascii=False, indent=2)}
"""


def local_rank_candidates(candidates: list[ReelCandidate], *, shortlist_count: int = 20) -> list[ReelCandidate]:
    def rank_key(candidate: ReelCandidate) -> tuple[float, float, float]:
        penalty = 0.0
        if "outside_source_chunk" in candidate.warnings:
            penalty += 3.0
        if "too_short" in candidate.warnings:
            penalty += 2.0
        if "too_long" in candidate.warnings:
            penalty += 1.0
        if "boundary_incomplete_end" in candidate.warnings:
            penalty += 2.5
        # A boundary-refined candidate is not a quality problem; it is expected
        # with small local models.
        soft_warning_count = len([
            warning
            for warning in candidate.warnings
            if warning not in {
                "boundary_refined",
                "composite_montage",
                "global_composite",
                "extended_for_complete_sentence",
            }
        ])
        ideal_duration = 22.0
        duration_penalty = min(1.0, abs(candidate.duration - ideal_duration) * 0.025)
        content_bonus = 0.25 if candidate.hook else 0.0
        content_bonus += 0.15 if candidate.reason else 0.0
        content_bonus += 0.35 if candidate.is_composite else 0.0
        content_bonus += 0.35 if "global_composite" in candidate.warnings else 0.0
        boundary_bonus = ((candidate.boundary_score or 50.0) - 50.0) / 100.0
        return (
            candidate.score - penalty - duration_penalty + content_bonus + boundary_bonus,
            -soft_warning_count,
            -candidate.duration,
        )

    return sorted(candidates, key=rank_key, reverse=True)[:shortlist_count]


def rank_candidates(
    candidates: list[ReelCandidate],
    client: OllamaClient,
    logs_dir: Path,
    *,
    shortlist_count: int = 20,
    target_count: int = 10,
    mode: str = "local",
    resume: bool = True,
    force_ollama: bool = False,
) -> list[ReelCandidate]:
    if not candidates:
        return []

    preselected = local_rank_candidates(candidates, shortlist_count=max(shortlist_count * 3, 30))

    if mode == "local":
        print(f"Local ranking: {len(preselected)} candidates")
        return preselected[:shortlist_count]

    cache_path = logs_dir / "ollama_ranking.impact_v2.selected.json"
    if resume and not force_ollama:
        cached = _load_cached_candidates(cache_path)
        if cached:
            print("Ollama ranking: cache")
            return cached[:shortlist_count]

    print(f"Ollama ranking: {len(preselected)} candidates")
    prompt = build_ranking_prompt(preselected, shortlist_count=shortlist_count, target_count=target_count)
    try:
        raw = client.generate(
            prompt,
            json_schema=ranking_response_schema(max_selected=shortlist_count),
        )
    except RuntimeError as exc:
        (logs_dir / "ollama_ranking.error.txt").write_text(str(exc), encoding="utf-8")
        print(f"  ranking skipped: {exc}")
        return preselected[:shortlist_count]
    (logs_dir / "ollama_ranking.txt").write_text(raw, encoding="utf-8")

    candidate_by_id = {c.id: c for c in preselected}
    ranked: list[ReelCandidate] = []
    try:
        payload = parse_json_loose(raw)
        items = payload.get("selected", []) if isinstance(payload, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get("candidate_id", "")).strip()
            candidate = candidate_by_id.get(candidate_id)
            if not candidate or candidate in ranked:
                continue
            improved_hook = str(item.get("improved_hook", "")).strip()
            if improved_hook:
                candidate.hook = improved_hook[:220]
            extra_reason = str(item.get("reason", "")).strip()
            if extra_reason:
                candidate.reason = extra_reason[:500]
            ranked.append(candidate)
    except Exception as exc:
        (logs_dir / "ollama_ranking.error.txt").write_text(str(exc), encoding="utf-8")

    if len(ranked) < shortlist_count:
        for candidate in preselected:
            if candidate not in ranked:
                ranked.append(candidate)
            if len(ranked) >= shortlist_count:
                break

    ranked = ranked[:shortlist_count]
    write_json(cache_path, [c.to_dict() for c in ranked])
    return ranked


def make_default_selections(shortlist: list[ReelCandidate], *, target_count: int) -> list[ReelSelection]:
    selections: list[ReelSelection] = []
    for rank, candidate in enumerate(shortlist[:target_count], start=1):
        selections.append(
            ReelSelection(
                id=f"R{rank:02d}",
                candidate_id=candidate.id,
                rank=rank,
                start=candidate.start,
                end=candidate.end,
                title=candidate.title,
                hook=candidate.hook,
                reason=candidate.reason,
                transcript_excerpt=candidate.transcript_excerpt,
                segments=list(candidate.source_segments) if candidate.is_composite else [],
            )
        )
    return selections


def interactive_select(shortlist: list[ReelCandidate], *, target_count: int) -> list[ReelSelection]:
    if not shortlist:
        return []

    cprint("\nShortlist IA:\n")
    for idx, candidate in enumerate(shortlist, start=1):
        visible_warnings = [
            warning
            for warning in candidate.warnings
            if warning not in {"boundary_refined", "composite_montage", "global_composite", "extended_for_complete_sentence"}
        ]
        warn = f" [WARN {','.join(visible_warnings)}]" if visible_warnings else ""
        refined = " [expanded]" if "boundary_refined" in candidate.warnings else ""
        montage_label = "montage global" if "global_composite" in candidate.warnings else "montage"
        montage = f" [{montage_label} {len(candidate.source_segments)} plans]" if candidate.is_composite else ""
        boundary = (
            f" | cut {candidate.boundary_score:.0f}/100 {candidate.boundary_method}"
            if candidate.boundary_score is not None
            else ""
        )
        cprint(
            f"{idx:02d}. {candidate.id} | {format_hms(candidate.start)}-{format_hms(candidate.end)} "
            f"| {candidate.duration:.0f}s | score {candidate.score:.1f}{boundary}{warn}{refined}{montage}\n"
            f"    {candidate.title}\n"
            f"    Hook: {candidate.hook}\n"
            f"    Raison: {candidate.reason}\n"
        )

    if len(shortlist) <= target_count:
        cprint(f"Shortlist <= cible ({len(shortlist)}/{target_count}) : selection automatique de tous les extraits.")
        return make_default_selections(shortlist, target_count=target_count)

    prompt = (
        f"Choisis {target_count} numeros separes par des virgules "
        f"(Entree = top {target_count}, 'q' = abandon): "
    )
    answer = input(prompt).strip()
    if answer.lower() in {"q", "quit", "exit"}:
        raise SystemExit("Abandon demande.")
    if not answer:
        return make_default_selections(shortlist, target_count=target_count)

    indexes: list[int] = []
    for part in answer.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part)
        except ValueError:
            continue
        if 1 <= idx <= len(shortlist) and idx not in indexes:
            indexes.append(idx)

    if not indexes:
        return make_default_selections(shortlist, target_count=target_count)

    selections: list[ReelSelection] = []
    for rank, idx in enumerate(indexes[:target_count], start=1):
        candidate = shortlist[idx - 1]
        selections.append(
            ReelSelection(
                id=f"R{rank:02d}",
                candidate_id=candidate.id,
                rank=rank,
                start=candidate.start,
                end=candidate.end,
                title=candidate.title,
                hook=candidate.hook,
                reason=candidate.reason,
                transcript_excerpt=candidate.transcript_excerpt,
                segments=list(candidate.source_segments) if candidate.is_composite else [],
            )
        )
    return selections


def save_analysis_outputs(
    output_dir: Path,
    candidates: list[ReelCandidate],
    shortlist: list[ReelCandidate],
    selections: list[ReelSelection],
) -> None:
    write_json(output_dir / "candidates.json", [c.to_dict() for c in candidates])
    write_json(output_dir / "shortlist.json", [c.to_dict() for c in shortlist])
    write_json(output_dir / "selected_reels.json", [s.to_dict() for s in selections])
