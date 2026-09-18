#!/usr/bin/env python3
"""Preuve ecran 2 (Brave) + multimodale pour Bob a reproduire.

Dispositif Peter :
  - Ecran 0 (gauche) : Grand Fantasia (audio en cours)
  - Ecran 1 / droite (ou est Cursor/Karen) : Brave (wiki / navigateur)

Ce script :
  1) Verifie Brave visible hors focus (side-window) sur moniteur >= 1
  2) Ouvre Chrome profil jetable sur l'ecran 2 (position x=2600)
  3) Fuse : fenetres + reseau + clavier/souris + audio_pc (simulation honnete
     OU event Ouie temp si --audio-ouie et Ouie dispo)
  4) Ferme Chrome jetable
  5) Ecrit traces/preuve-ecran2-multimodal.jsonl

Limite vision : contenu = TITRE de fenetre, pas OCR/pixels (ADR-0002/0005).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.adapters.ouie_system import adapt_ouie_system  # noqa: E402
from fusion_layer.adapters.texte import adapt_texte  # noqa: E402
from fusion_layer.capteurs.clavier_souris import sample_input_activity  # noqa: E402
from fusion_layer.capteurs.fenetre_active import sample_screen_context  # noqa: E402
from fusion_layer.capteurs.reseau import sample_network  # noqa: E402
from fusion_layer.cli import _ollama_chat  # noqa: E402
from fusion_layer.contract import FusionEvent  # noqa: E402
from fusion_layer.fuser import fuse  # noqa: E402
from fusion_layer.trace import write_trace  # noqa: E402

OUT = ROOT / "traces" / "preuve-ecran2-multimodal.jsonl"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def _audio_event(*, simulate: bool) -> FusionEvent:
    if simulate:
        # Honnete : on N'A PAS ecoute le loopback ici (ADR-0005).
        raw = {
            "type": "media.playback",
            "label": "unknown",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000+02:00", time.localtime()),
            "device": "pc",
            "channel": "system",
            "confidence": 0.3,
            "duration_s": 30.0,
            "meta": {
                "schema": "lyla-ouie/ambient-event@1",
                "phase": "B2",
                "confidence_kind": "heuristic_match",
                "app": "GrandFantasia.exe",
            },
        }
        ev = adapt_ouie_system(raw)
        from dataclasses import replace

        return replace(
            ev,
            text=f"[SIMULATION audio_pc, pas une ecoute reelle ce run] {ev.text}",
            ts_origin="fixture_simulee",
            ts_wall_ms=int(time.time() * 1000),
        ).validate()
    raise RuntimeError("audio reel : utiliser Bob/Ouie temp (hors ce script)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", type=float, default=6.0)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-chrome", action="store_true")
    ap.add_argument(
        "--audio-simule",
        action="store_true",
        default=True,
        help="marque audio_pc comme simulation (defaut)",
    )
    args = ap.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    # 1) Snapshot avant Chrome
    wins0 = sample_screen_context()
    row0 = {
        "step": "avant_chrome",
        "windows": [
            {
                "exe": (w.facets or {}).get("exe"),
                "mon": (w.facets or {}).get("monitor_index"),
                "focus": (w.facets or {}).get("focus"),
                "titre": (w.text or "")[:160],
            }
            for w in wins0
        ],
    }
    brave_seen = any(
        (w.facets or {}).get("exe", "").lower().startswith("brave") for w in wins0
    )
    brave_on_m1 = any(
        (w.facets or {}).get("exe", "").lower().startswith("brave")
        and (w.facets or {}).get("monitor_index") == "1"
        for w in wins0
    )
    row0["brave_visible"] = brave_seen
    row0["brave_sur_moniteur_1"] = brave_on_m1
    rows.append(row0)
    print("AVANT", json.dumps(row0, ensure_ascii=False, indent=2))

    chrome_proc = None
    profile = None
    if not args.no_chrome and CHROME.is_file():
        profile = Path(tempfile.mkdtemp(prefix="fusion-chrome-m1-"))
        # Ecran 2 commence a x=2560
        cmd = [
            str(CHROME),
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--new-window",
            "--window-position=2700,220",
            "--window-size=1100,800",
            "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
        ]
        print("OPEN Chrome ecran2", cmd[-1])
        chrome_proc = subprocess.Popen(cmd)
        time.sleep(args.watch)

    try:
        now = int(time.time() * 1000)
        net = sample_network(measure_activity=True)
        act = sample_input_activity()
        wins = sample_screen_context()
        audio = _audio_event(simulate=True)
        q = adapt_texte(
            "Resume le contexte multimodal : jeu, navigateur(s), saisie, reseau "
            "(et audio seulement s'il est marque comme mesure reelle).",
            ts_wall_ms=now,
        )
        result = fuse([net, act, audio, *wins, q], now_ms=now)
        row = {
            "step": "fuse_multimodal",
            "windows": [
                {
                    "exe": (w.facets or {}).get("exe"),
                    "cat": (w.facets or {}).get("category"),
                    "mon": (w.facets or {}).get("monitor_index"),
                    "focus": (w.facets or {}).get("focus"),
                    "titre": (w.text or "")[:180],
                }
                for w in wins
            ],
            "activity": act.text,
            "network": net.text,
            "audio": audio.text,
            "conflicts": [c.rule for c in result.conflicts],
            "packet": result.packet.text,
            "brave_in_packet": "brave" in result.packet.text.lower(),
            "gf_in_packet": "grandfantasia" in result.packet.text.lower(),
            "contenu_lu": "titre de fenetre uniquement (pas OCR)",
        }
        if not args.no_llm:
            reply, proof = _ollama_chat(result.packet.text)
            row["llm_reply"] = reply
            row["llm_proof"] = proof
            write_trace(result, proof)
            row["llm_ok"] = bool((reply or "").strip())
        rows.append(row)
        print("PACKET_BEGIN")
        print(result.packet.text)
        print("PACKET_END")
        if row.get("llm_reply"):
            print("REPLY_BEGIN")
            print(row["llm_reply"])
            print("REPLY_END")

        ok = (
            row["brave_in_packet"]
            and row["gf_in_packet"]
            and row0.get("brave_visible")
            and (args.no_llm or row.get("llm_ok"))
        )
        resume = {
            "ok": ok,
            "brave_visible_avant": row0.get("brave_visible"),
            "brave_moniteur_1": row0.get("brave_sur_moniteur_1"),
            "brave_in_packet": row["brave_in_packet"],
            "gf_in_packet": row["gf_in_packet"],
            "audio": "SIMULATION marquee (pas Ouie live dans ce run Karen)",
            "vision": "titres fenetre multi-ecran (pas pixels)",
            "protocole_bob": (
                "Meme script sur le poste Bob : ecran ou sont Claude+Brave = moniteur "
                "de droite ; lancer python scripts/preuve_ecran2_multimodal.py"
            ),
        }
        print("==== RESUME ====")
        print(json.dumps(resume, ensure_ascii=False, indent=2))
        with OUT.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.write(json.dumps({"resume": resume}, ensure_ascii=False) + "\n")
        (ROOT / "traces" / "preuve-ecran2-multimodal-resume.json").write_text(
            json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 0 if ok else 1
    finally:
        if chrome_proc is not None:
            print("CLOSE Chrome jetable")
            subprocess.run(
                ["taskkill", "/PID", str(chrome_proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            try:
                chrome_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            if profile:
                # Chrome tient encore ses fichiers juste apres taskkill : un seul
                # essai laissait le profil dans %TEMP% (constate 18/09, Bob).
                for _ in range(10):
                    shutil.rmtree(profile, ignore_errors=True)
                    if not profile.exists():
                        break
                    time.sleep(0.5)
                if profile.exists():
                    print(f"PROFIL RESTANT {profile}")


if __name__ == "__main__":
    raise SystemExit(main())
