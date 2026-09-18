"""Adaptateur Lyla-Ouïe system / ambient → audio_pc."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fusion_layer.adapters.base import conf_from_prob, iso_to_wall_ms, iter_jsonl
from fusion_layer.config import DEFAULT_CONFIG, FusionConfig
from fusion_layer.contract import ContractError, FusionEvent


def adapt_ouie_system(raw: dict[str, Any], cfg: FusionConfig | None = None) -> FusionEvent:
    cfg = cfg or DEFAULT_CONFIG
    type_ = str(raw.get("type") or "")
    label = str(raw.get("label") or "unknown")
    if not type_:
        raise ContractError("system: type obligatoire")
    ts = raw.get("ts")
    if not ts:
        raise ContractError("system: ts obligatoire")
    conf_raw = raw.get("confidence")
    try:
        conf_f = float(conf_raw) if conf_raw is not None else None
    except (TypeError, ValueError):
        conf_f = None
    level, conf_f = conf_from_prob(conf_f)
    duration = raw.get("duration_s")
    try:
        duration_f = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_f = None
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    # Ouie declare ce que mesure sa confiance (ex. « heuristic_match » en B2).
    # On le reprend tel quel : l'etiqueter « classifier_prob » presentait une
    # heuristique comme une probabilite (vu sur un vrai event, Bob 18/09).
    conf_kind = str(meta.get("confidence_kind") or "classifier_prob")
    # programme qui produit le son (nom d'executable seulement, jamais la liste)
    app = str(meta.get("app") or "").strip()
    text = f"{type_}/{label}"
    if duration_f is not None:
        text += f" duration_s={duration_f:.1f}"
    if app:
        text += f" app_son={app}"
    # meme forme d'event pour la sortie PC et le micro ambiant : le canal tranche
    channel = str(raw.get("channel") or "system")
    modality = "audio_pc" if channel == "system" else "audio_scene"
    return FusionEvent(
        id=str(raw.get("id") or ""),
        modality=modality,
        source_project="Lyla-Ouie",
        source_type="lyla-ouie/ambient-event@1",
        ts_wall_ms=iso_to_wall_ms(str(ts)),
        ts_origin="ts_iso",
        valid_ms=None,
        kind="etat",
        text=text,
        confidence=level,
        confidence_raw=conf_f,
        confidence_kind=conf_kind if conf_f is not None else None,
        untrusted=False,
        facets={"app": app} if app else None,
    ).validate()


def adapt_ouie_system_jsonl(
    path: Path, cfg: FusionConfig | None = None
) -> list[FusionEvent]:
    out: list[FusionEvent] = []
    for obj in iter_jsonl(path):
        try:
            out.append(adapt_ouie_system(obj, cfg))
        except ContractError:
            continue
    return out
