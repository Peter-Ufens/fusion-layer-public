#!/usr/bin/env python3
"""Preuve : objectif de concentration (navigateur / jeu / Cursor).

Question de Peter : si on demande au LLM de se concentrer sur UNE fenetre,
qu'est-ce qu'il recoit vraiment (vision titre, audio, saisie, reseau) ?

Reponse honnete V1 :
  - Vision = TITRE de fenetre Windows uniquement (pas le texte de la page,
    pas OCR, pas pixels).
  - Audio PC = simulation marquee ici (ADR-0005), sauf si --audio-reel plus tard.
  - Saisie = actif/idle global (pas quelle touche).
  - Reseau = sonde TCP.

Trois questions sur LE MEME paquet d'observations.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.adapters.ouie_system import adapt_ouie_system  # noqa: E402
from fusion_layer.adapters.texte import adapt_texte  # noqa: E402
from fusion_layer.capteurs.clavier_souris import sample_input_activity  # noqa: E402
from fusion_layer.capteurs.fenetre_active import sample_screen_context  # noqa: E402
from fusion_layer.capteurs.reseau import sample_network  # noqa: E402
from fusion_layer.cli import CONSIGNE_SYSTEME, _ollama_chat  # noqa: E402
from fusion_layer.contract import FusionEvent  # noqa: E402
from fusion_layer.fuser import fuse  # noqa: E402
from fusion_layer.trace import write_trace  # noqa: E402

OUT = ROOT / "traces" / "preuve-focus-objectif.jsonl"
RESUME = ROOT / "traces" / "preuve-focus-objectif-resume.json"

OBJECTIFS = [
    {
        "id": "navigateur",
        "question": (
            "OBJECTIF : concentre-toi UNIQUEMENT sur le navigateur (Brave/Chrome). "
            "Que vois-tu exactement affiche dans ce navigateur ? "
            "Cite le titre. Dis clairement si tu lis le corps de la page "
            "(paragraphes, wiki) ou seulement le titre de fenetre. "
            "N'invente aucun texte de page."
        ),
    },
    {
        "id": "jeu",
        "question": (
            "OBJECTIF : concentre-toi UNIQUEMENT sur la fenetre de jeu "
            "(Grand Fantasia). Y a-t-il de l'activite sur cette fenetre ? "
            "Que vois-tu (titre, focus, moniteur) ? Que dis-tu du SON "
            "(audio_pc) : mesure reelle ou simulation ? "
            "La saisie clavier/souris va-t-elle a ce jeu (regarde focus=oui) ?"
        ),
    },
    {
        "id": "cursor",
        "question": (
            "OBJECTIF : concentre-toi UNIQUEMENT sur Cursor (IDE/agent). "
            "Quel titre de fenetre vois-tu ? Y a-t-il un nom de projet / "
            "workspace / fichier visible dans ce titre ? "
            "Sur quel moniteur ? focus oui ou non ?"
        ),
    },
]


def _audio_simulation() -> FusionEvent:
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


def main() -> int:
    now = int(time.time() * 1000)
    wins = sample_screen_context()
    net = sample_network(measure_activity=True)
    act = sample_input_activity()
    audio = _audio_simulation()

    win_rows = [
        {
            "exe": (w.facets or {}).get("exe"),
            "cat": (w.facets or {}).get("category"),
            "mon": (w.facets or {}).get("monitor_index"),
            "focus": (w.facets or {}).get("focus"),
            "titre_extrait": (w.text or "")[:220],
        }
        for w in wins
    ]
    print("FENETRES_VUUES")
    print(json.dumps(win_rows, ensure_ascii=False, indent=2))

    # Paquet de base sans question (on injecte la question par objectif)
    base_events = [net, act, audio, *wins]

    consigne = (
        CONSIGNE_SYSTEME
        + " Quand un OBJECTIF nomme une fenetre, reponds d'abord sur cette "
        "fenetre. Distingue clairement : (1) titre de fenetre lu, "
        "(2) corps de page / pixels (non mesure en V1), "
        "(3) audio reel vs simulation, (4) qui a le focus pour la saisie."
    )

    rows: list[dict] = [{"step": "snapshot", "windows": win_rows}]
    answers: dict[str, dict] = {}

    for obj in OBJECTIFS:
        q = adapt_texte(obj["question"], ts_wall_ms=now)
        result = fuse([*base_events, q], now_ms=now)
        reply, proof = _ollama_chat(result.packet.text, consigne=consigne)
        write_trace(result, proof)
        row = {
            "step": f"objectif_{obj['id']}",
            "question": obj["question"],
            "packet": result.packet.text,
            "llm_reply": reply,
            "llm_ok": bool((reply or "").strip()),
        }
        rows.append(row)
        answers[obj["id"]] = {
            "question_courte": obj["id"],
            "llm_reply": reply,
            "llm_ok": row["llm_ok"],
        }
        print(f"\n==== OBJECTIF {obj['id'].upper()} ====")
        print("PACKET_BEGIN")
        print(result.packet.text)
        print("PACKET_END")
        print("REPLY_BEGIN")
        print(reply)
        print("REPLY_END")

    # Verdict honnete (code, pas LLM)
    packet_all = "\n".join(r.get("packet", "") for r in rows if "packet" in r)
    verdict = {
        "vision_lit_corps_page": False,
        "vision_lit_titre_fenetre": True,
        # Presence par programme, pas par mots d'onglet (Bob L8 : faux negatif
        # des que l'onglet n'est plus le wiki Fandom du test Karen).
        "preuve_brave_dans_paquet": "brave" in packet_all.lower()
        or any(
            (w.get("exe") or "").lower().startswith("brave") for w in win_rows
        ),
        "preuve_cursor_dans_paquet": "cursor" in packet_all.lower()
        or any(
            (w.get("exe") or "").lower().startswith("cursor") for w in win_rows
        ),
        "preuve_jeu_dans_paquet": "grandfantasia" in packet_all.lower()
        or any(
            (w.get("exe") or "").lower().startswith("grandfantasia")
            for w in win_rows
        ),
        "audio_ce_run": "SIMULATION marquee (pas Ouie live)",
        "saisie": act.text,
        "reseau": net.text,
        "nuance_v1": (
            "Demander au LLM de se concentrer sur le navigateur ne lui donne "
            "PAS le texte de la page : seulement le titre de la barre de titre. "
            "Sur le jeu : titre + focus + moniteur ; le son n'est reel que si "
            "Ouie mesure (ici simulation). Sur Cursor : titre IDE (projet/"
            "fichier s'ils apparaissent dans le titre Windows)."
        ),
        "objectifs": answers,
        "ok": all(a.get("llm_ok") for a in answers.values())
        and any((w.get("exe") or "").lower().startswith("brave") for w in win_rows)
        and any(
            (w.get("exe") or "").lower().startswith("grandfantasia") for w in win_rows
        ),
    }
    print("\n==== VERDICT ====")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.write(json.dumps({"verdict": verdict}, ensure_ascii=False) + "\n")
    RESUME.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
