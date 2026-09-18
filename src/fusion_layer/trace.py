"""Trace locale des paquets, hors Git (ADR-0003 §6) + preuve LLM (ADR-0004 §6).

Une ligne JSONL par paquet : ids retenus / ecartes avec raison, conflits,
question, et ce qu'Ollama a renvoye (modele, digest, durees, jetons). C'est
cette trace qui demontre quel LLM a repondu.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from fusion_layer.fuser import FuseResult

ROOT = Path(__file__).resolve().parents[2]
TRACE_FILE = ROOT / "traces" / "fusion-trace.jsonl"
OLLAMA = "http://127.0.0.1:11434"
_NS_PAR_MS = 1_000_000


def model_digest(model: str, base_url: str = OLLAMA, timeout: float = 10) -> str | None:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return next(
        (m.get("digest") for m in tags.get("models", []) if m.get("name") == model), None
    )


def llm_proof(response: dict[str, Any], model: str, digest: str | None, wall_ms: int) -> dict[str, Any]:
    return {
        "model_demande": model,
        "model_repondu": response.get("model"),
        "digest": digest,
        "load_ms": (response.get("load_duration") or 0) // _NS_PAR_MS,
        "total_ms": (response.get("total_duration") or 0) // _NS_PAR_MS,
        "eval_count": response.get("eval_count"),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "wall_ms": wall_ms,
    }


def write_trace(
    result: FuseResult, llm: dict[str, Any] | None = None, path: Path | None = None
) -> Path:
    path = path or TRACE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "t_wall_ms": int(time.time() * 1000),
        "question": result.question,
        "packet": result.packet.to_dict(),
        "llm": llm,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
