"""Adaptateur Lyla-Vision screen.context → vision_screen."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fusion_layer.adapters.base import conf_from_vision_level, iter_jsonl, truncate
from fusion_layer.config import DEFAULT_CONFIG, FusionConfig
from fusion_layer.contract import ContractError, FusionEvent


def adapt_vision_screen(
    raw: dict[str, Any],
    cfg: FusionConfig | None = None,
    *,
    source_project: str = "Lyla-Vision",
    source_type: str = "screen.context",
    ts_origin_override: str | None = None,
) -> FusionEvent:
    """`source_project` / `source_type` : un producteur qui n'est pas Lyla-Vision
    (sonde web de la CLI) se declare comme tel, la trace ne doit pas mentir."""
    cfg = cfg or DEFAULT_CONFIG
    typ = raw.get("type")
    if typ is not None and typ != "screen.context":
        raise ContractError("vision: type attendu screen.context")
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
    if not isinstance(payload, dict):
        raise ContractError("vision: payload manquant")

    # horloge murale
    ts_wall_ms = payload.get("t_wall_ms")
    ts_origin = "payload.t_wall_ms"
    if ts_wall_ms is None and "t_wall_s" in raw:
        try:
            ts_wall_ms = int(float(raw["t_wall_s"]) * 1000)
            ts_origin = "t_wall_s_emit"
        except (TypeError, ValueError):
            ts_wall_ms = None
    if ts_wall_ms is None:
        raise ContractError("no_wall_clock")
    try:
        ts_wall_ms = int(ts_wall_ms)
    except (TypeError, ValueError) as exc:
        raise ContractError("no_wall_clock") from exc

    process = payload.get("process") if isinstance(payload.get("process"), dict) else {}
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    category = str(process.get("category") or "unknown")

    # refus explicite d'abord, puis liste blanche stricte si elle est non vide
    if category in cfg.screen_categories_deny or (
        cfg.screen_categories_allow and category not in cfg.screen_categories_allow
    ):
        raise ContractError(f"screen_category_denied:{category}")

    host = document.get("host") or ""
    title = window.get("title") or ""
    exe = process.get("exe_name") or process.get("label") or ""
    parts = [
        f"app={exe}" if exe else None,
        f"host={host}" if host else None,
        f"categorie={category}",
        f"titre={title}" if title else None,
    ]
    text = truncate(" ".join(p for p in parts if p), cfg.budget_screen_chars)

    level_src = payload.get("confidence")
    conf_float = raw.get("conf")
    try:
        conf_f = float(conf_float) if conf_float is not None else None
    except (TypeError, ValueError):
        conf_f = None
    level, conf_f = conf_from_vision_level(
        str(level_src) if level_src is not None else None, conf_f
    )

    return FusionEvent(
        id=str(raw.get("id") or ""),
        modality="vision_screen",
        source_project=source_project,
        source_type=source_type,
        ts_wall_ms=ts_wall_ms,
        ts_origin=ts_origin_override or ts_origin,
        valid_ms=None,
        kind="etat",
        text=text,
        confidence=level,
        confidence_raw=conf_f,
        confidence_kind="vision_level",
        untrusted=True,
        facets={"category": category},
    ).validate()


def adapt_vision_screen_jsonl(
    path: Path, cfg: FusionConfig | None = None
) -> list[FusionEvent]:
    out: list[FusionEvent] = []
    for obj in iter_jsonl(path):
        if obj.get("type") not in (None, "screen.context"):
            continue
        try:
            out.append(adapt_vision_screen(obj, cfg))
        except ContractError:
            continue
    return out
