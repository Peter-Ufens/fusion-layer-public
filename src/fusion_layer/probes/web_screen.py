"""Synthese d'events ecran a partir d'URL / titre (probe autonome, pas Lyla-Vision)."""
from __future__ import annotations

import time
from urllib.parse import urlparse

from fusion_layer.adapters.vision_screen import adapt_vision_screen
from fusion_layer.config import FusionConfig
from fusion_layer.contract import FusionEvent


MEDIA_HOSTS = ("youtube.", "youtu.be", "vimeo.", "netflix.", "twitch.")


def screen_event_from_web(
    *,
    url: str,
    title: str,
    app: str = "browser",
    category: str | None = None,
    ts_wall_ms: int | None = None,
    cfg: FusionConfig | None = None,
) -> FusionEvent:
    """Construit un event vision_screen compatible via la forme screen.context.

    Provenance honnete : source `Fusion-Layer` / `fusion/web-probe@1`, heure
    `saisie_cli`. Rien n'a ete vu par Lyla-Vision, l'URL et le titre sont tapes.
    """
    host = urlparse(url).hostname or ""
    # youtube / vimeo / etc. = media ; sinon browser (sauf categorie imposee)
    if category is not None:
        cat = category
    elif host and any(h in host for h in MEDIA_HOSTS):
        cat = "media"
    else:
        cat = "browser"
    now = ts_wall_ms if ts_wall_ms is not None else int(time.time() * 1000)
    raw = {
        "type": "screen.context",
        "id": f"evt_probe_web_{now}",
        "conf": 0.8,
        "payload": {
            "t_wall_ms": now,
            "confidence": "high",
            "process": {"exe_name": app, "category": cat},
            "document": {"host": host, "url": url},
            "window": {"title": title},
        },
    }
    return adapt_vision_screen(
        raw,
        cfg,
        source_project="Fusion-Layer",
        source_type="fusion/web-probe@1",
        ts_origin_override="saisie_cli",
    )
