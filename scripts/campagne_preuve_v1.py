#!/usr/bin/env python3
"""Campagne de preuve V1 · 20+ iterations live (ADR-0005 autonome).

Usage:
  set PYTHONPATH=src
  python scripts/campagne_preuve_v1.py
  python scripts/campagne_preuve_v1.py --rounds 25 --llm-every 5
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.adapters.texte import adapt_texte  # noqa: E402
from fusion_layer.capteurs.clavier_souris import sample_input_activity  # noqa: E402
from fusion_layer.capteurs.fenetre_active import sample_screen_context  # noqa: E402
from fusion_layer.capteurs.reseau import sample_network  # noqa: E402
from fusion_layer.cli import _ollama_chat  # noqa: E402
from fusion_layer.fuser import fuse  # noqa: E402

OUT = ROOT / "traces" / "campagne-preuve-v1.jsonl"
RESUME = ROOT / "traces" / "campagne-preuve-v1-resume.json"
GAME_MARKERS = ("grandfantasia", "grand fantasia")


def _is_game(ev) -> bool:
    facets = ev.facets or {}
    if facets.get("category") == "game":
        return True
    blob = f"{ev.text or ''} {facets.get('exe', '')}".lower()
    return any(m in blob for m in GAME_MARKERS)


def one_round(i: int, *, with_llm: bool, measure_net: bool) -> dict:
    t0 = time.perf_counter()
    failles: list[str] = []

    # Round sans mesure reseau : AUCUN event reseau. Avant (Bob 18/09), un
    # connect simule fabriquait « latence_ms=0 verdict=stable » envoye au LLM
    # comme une vraie mesure (rounds LLM 5, 10, 20 sur 20).
    net = sample_network(measure_activity=True) if measure_net else None

    act = sample_input_activity()
    wins = sample_screen_context()
    now = int(time.time() * 1000)
    q = adapt_texte(
        "Est-ce que je joue (clavier/souris) et quelle fenetre de jeu est visible ?",
        ts_wall_ms=now,
    )
    result = fuse([*([net] if net else []), act, *wins, q], now_ms=now)

    if not wins:
        failles.append("FAIL_aucune_fenetre")
    if act.text is None:
        failles.append(f"FAIL_activite:{act.text_null_reason}")
    if not result.packet.text.strip():
        failles.append("FAIL_paquet_vide")
    if result.question is None:
        failles.append("FAIL_question_absente")
    if net and re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", net.text or ""):
        failles.append("FAIL_ip_dans_texte_reseau")
    if "latence_ms=0 gigue_ms=0" in result.packet.text:
        failles.append("FAIL_reseau_fabrique_dans_le_paquet")

    games = [w for w in wins if _is_game(w)]
    game_seen = bool(games)
    etat = (act.facets or {}).get("etat")

    # Jeu visible + saisie longue : suspect (manette / AFK / focus ailleurs)
    if game_seen and etat == "sans_saisie_longue":
        failles.append("WARN_jeu_visible_sans_saisie_longue")

    mon_counts = [(w.facets or {}).get("monitor_count") for w in wins]
    if wins and all(int(m or "0") < 1 for m in mon_counts):
        failles.append("WARN_monitor_count_0")

    # Plusieurs vision_screen doivent survivre au fuse (jeu + focus)
    vision_obs = [e for e in result.observation_events if e.modality == "vision_screen"]
    if len(wins) >= 2 and len(vision_obs) < 2:
        failles.append(
            f"FAIL_fuse_ecrase_multi_ecran wins={len(wins)} obs_vision={len(vision_obs)}"
        )

    reply = None
    proof = None
    if with_llm:
        try:
            reply, proof = _ollama_chat(result.packet.text)
            if not (reply or "").strip():
                failles.append("FAIL_llm_content_vide")
        except Exception as exc:
            failles.append(f"FAIL_llm:{exc}")

    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "round": i,
        "ms": ms,
        "network_verdict": (net.facets or {}).get("verdict") if net else "non_mesure",
        "network_text": net.text if net else None,
        "activity_etat": etat,
        "activity_text": act.text,
        "windows": [
            {
                "exe": (w.facets or {}).get("exe"),
                "category": (w.facets or {}).get("category"),
                "focus": (w.facets or {}).get("focus"),
                "monitor": (w.facets or {}).get("monitor_index"),
                "text": w.text or w.text_null_reason,
            }
            for w in wins
        ],
        "game_visible": game_seen,
        "vision_obs_count": len(vision_obs),
        "conflicts": [c.rule for c in result.conflicts],
        "question": result.question,
        "packet_excerpt": result.packet.text[:600],
        "llm_reply_excerpt": (reply or "")[:400] if reply else None,
        "llm_proof": proof,
        "failles": failles,
        "ok": not any(f.startswith("FAIL") for f in failles),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=20)
    ap.add_argument("--sleep", type=float, default=1.5)
    ap.add_argument("--llm-every", type=int, default=5)
    ap.add_argument("--net-every", type=int, default=3)
    args = ap.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    print(f"campagne rounds={args.rounds} out={OUT}")
    fail_rounds = 0
    warn_rounds = 0
    all_failles: list[str] = []

    for i in range(1, args.rounds + 1):
        with_llm = args.llm_every > 0 and (i % args.llm_every == 0)
        measure_net = i % max(1, args.net_every) == 0
        row = one_round(i, with_llm=with_llm, measure_net=measure_net)
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        status = "OK" if row["ok"] else "FAIL"
        if any(x.startswith("WARN") for x in row["failles"]):
            warn_rounds += 1
        if not row["ok"]:
            fail_rounds += 1
        all_failles.extend(row["failles"])
        exes = ",".join(str(w.get("exe")) for w in row["windows"])
        print(
            f"[{i:02d}/{args.rounds}] {status} {row['ms']}ms "
            f"exes=[{exes}] etat={row['activity_etat']} "
            f"game={row['game_visible']} vision_obs={row['vision_obs_count']} "
            f"failles={row['failles']}"
        )
        if i < args.rounds:
            time.sleep(args.sleep)

    counts = Counter(all_failles)
    resume = {
        "rounds": args.rounds,
        "fail_rounds": fail_rounds,
        "warn_rounds": warn_rounds,
        "failles_counts": dict(counts),
    }
    RESUME.write_text(json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8")
    print("==== RESUME ====")
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    print(f"resume={RESUME}")
    return 1 if fail_rounds else 0


if __name__ == "__main__":
    raise SystemExit(main())
