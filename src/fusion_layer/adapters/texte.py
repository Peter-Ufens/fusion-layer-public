"""Adaptateur texte (saisie Peter / Lyla-App)."""
from __future__ import annotations

import time
from typing import Any

from fusion_layer.config import DEFAULT_CONFIG, FusionConfig
from fusion_layer.contract import FusionEvent


def adapt_texte(
    text: str,
    *,
    ts_wall_ms: int | None = None,
    cfg: FusionConfig | None = None,
    source_project: str = "Lyla-App",
) -> FusionEvent:
    cfg = cfg or DEFAULT_CONFIG
    return FusionEvent(
        modality="text",
        source_project=source_project,
        source_type="fusion/text-input@1",
        ts_wall_ms=ts_wall_ms or int(time.time() * 1000),
        ts_origin="fixture" if ts_wall_ms else "wall_now",
        valid_ms=cfg.text_valid_ms,
        kind="ponctuel",
        text=text.strip(),
        confidence="high",
        speaker_role="peter",
        untrusted=False,
    ).validate()


def adapt_texte_dict(raw: dict[str, Any], cfg: FusionConfig | None = None) -> FusionEvent:
    return adapt_texte(
        str(raw.get("text") or ""),
        ts_wall_ms=int(raw["ts_wall_ms"]) if raw.get("ts_wall_ms") else None,
        cfg=cfg,
        source_project=str(raw.get("source_project") or "Lyla-App"),
    )
