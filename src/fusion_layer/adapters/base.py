"""Helpers communs aux adaptateurs."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from fusion_layer.contract import ContractError


def iso_to_wall_ms(ts: str) -> int:
    """ISO 8601 avec fuseau explicite → epoch ms.

    Une date sans fuseau est refusee : on ne sait pas quelle heure murale elle
    designe (ADR-0003 regle 1). Une date illisible leve ContractError, pas
    ValueError, pour qu'une seule ligne cassee ne fasse pas tomber tout un JSONL.
    """
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ContractError(f"ts_illisible:{ts!r}") from exc
    if dt.tzinfo is None:
        raise ContractError(f"ts_sans_fuseau:{ts!r}")
    return int(dt.timestamp() * 1000)


def conf_from_vision_level(
    level: str | None, conf_float: float | None = None
) -> tuple[str, float | None]:
    mapping = {"high": 0.95, "medium": 0.80, "low": 0.45, "unknown": 0.0}
    if level in mapping:
        return level, mapping[level] if conf_float is None else conf_float
    if conf_float is None:
        return "unknown", None
    if conf_float >= 0.9:
        return "high", conf_float
    if conf_float >= 0.7:
        return "medium", conf_float
    if conf_float > 0:
        return "low", conf_float
    return "unknown", conf_float


def conf_from_prob(p: float | None) -> tuple[str, float | None]:
    if p is None:
        return "unknown", None
    if p >= 0.85:
        return "high", p
    if p >= 0.6:
        return "medium", p
    if p > 0:
        return "low", p
    return "unknown", p


def degrade_by_no_speech(level: str, no_speech_prob: float | None) -> str:
    """no_speech_prob ne peut que degrader (ADR-0003)."""
    if no_speech_prob is None:
        return level
    order = ["high", "medium", "low", "unknown"]
    idx = order.index(level) if level in order else 3
    if no_speech_prob >= 0.6:
        idx = min(3, idx + 2)
    elif no_speech_prob >= 0.35:
        idx = min(3, idx + 1)
    return order[idx]


def truncate(text: str, budget: int) -> str:
    t = text.strip()
    if len(t) <= budget:
        return t
    return t[: max(0, budget - 15)].rstrip() + " …[tronque]"


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def speaker_to_role(speaker: str | None) -> str:
    """Role mesure sur la voix. Jamais un nom de tiers dans le contrat Fusion.

    Seul `speaker` (mesure par Ouie) compte. Le champ `source` d'Ouie est ce qui
    est declare a l'avance (le micro de Peter) : il ne prouve pas qui parle. Le
    contrat Ouie le dit lui-meme, les deux peuvent differer. Sans mesure, le role
    est donc `inconnu`, sinon le dialogue d'un film capte par le micro deviendrait
    « la question de Peter ».
    """
    measured = (speaker or "").strip().lower()
    if measured in {"peter", "lunanel"}:
        return "peter"
    if not measured or measured in {"unknown", "inconnu"}:
        return "inconnu"
    return "autre_voix"
