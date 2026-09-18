"""Adaptateur Lyla-Ouïe STT → FusionEvent speech."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fusion_layer.adapters.base import (
    degrade_by_no_speech,
    iso_to_wall_ms,
    iter_jsonl,
    speaker_to_role,
    truncate,
)
from fusion_layer.config import DEFAULT_CONFIG, FusionConfig
from fusion_layer.contract import ContractError, FusionEvent


def adapt_ouie_stt(raw: dict[str, Any], cfg: FusionConfig | None = None) -> FusionEvent:
    cfg = cfg or DEFAULT_CONFIG
    if "text" not in raw or "ts" not in raw:
        raise ContractError("STT: champs text/ts obligatoires")
    text = truncate(str(raw["text"]), cfg.budget_speech_chars)
    ts_wall_ms = iso_to_wall_ms(str(raw["ts"]))
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    no_speech = meta.get("no_speech_prob")
    try:
        no_speech_f = float(no_speech) if no_speech is not None else None
    except (TypeError, ValueError):
        no_speech_f = None
    level = degrade_by_no_speech("unknown", no_speech_f)
    role = speaker_to_role(raw.get("speaker"))
    conf_raw = raw.get("speaker_confidence")
    conf_kind = "speaker_similarity" if conf_raw is not None else (
        "no_speech_prob" if no_speech_f is not None else None
    )
    try:
        conf_raw_f = float(conf_raw) if conf_raw is not None else (
            no_speech_f if no_speech_f is not None else None
        )
    except (TypeError, ValueError):
        conf_raw_f = None
    return FusionEvent(
        id=str(raw.get("id") or ""),
        modality="speech",
        source_project="Lyla-Ouie",
        source_type="lyla-ouie/stt-event@1",
        ts_wall_ms=ts_wall_ms,
        ts_origin="ts_iso",
        valid_ms=cfg.speech_valid_ms,
        kind="ponctuel",
        text=text,
        confidence=level,
        confidence_raw=conf_raw_f,
        confidence_kind=conf_kind,
        speaker_role=role,
        untrusted=True,
    ).validate()


def adapt_ouie_stt_jsonl(
    path: Path, cfg: FusionConfig | None = None
) -> list[FusionEvent]:
    out: list[FusionEvent] = []
    for obj in iter_jsonl(path):
        try:
            out.append(adapt_ouie_stt(obj, cfg))
        except ContractError:
            continue
    return out
