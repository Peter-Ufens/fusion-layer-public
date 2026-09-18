#!/usr/bin/env python3
"""Banc de consigne LLM : N formulations x 4 scenarios (jeu au premier plan / hors focus).

A rejouer AVANT toute retouche de `cli.CONSIGNE_JEU` (Bob 18/09 : une retouche
de bonne foi avait fait dire « vous jouez » avec le jeu hors focus).

Usage :
  python scripts/banc_consigne_llm.py                  # toutes les consignes
  python scripts/banc_consigne_llm.py C_focus_dabord   # une seule

Exige Ollama local et le modele de config (qwen3.5:9b-gpu). Lire les reponses en entier.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fusion_layer.adapters.texte import adapt_texte
from fusion_layer.capteurs.clavier_souris import sample_input_activity
from fusion_layer.capteurs.fenetre_active import _event_from_raw
from fusion_layer.cli import CONSIGNE_BASE, CONSIGNE_JEU, _ollama_chat
from fusion_layer.config import DEFAULT_CONFIG
from fusion_layer.fuser import fuse

CANDIDATES = {
    "K_karen": CONSIGNE_BASE
    + "Si app=*.exe categorie=game et etat=actif apparaissent ensemble, tu peux dire que le jeu "
    "est au premier plan avec saisie recente, sans affirmer l'identite du joueur.",
    "B_bob_v1": CONSIGNE_BASE
    + "Si une fenetre categorie=game a focus=oui et que etat=actif, tu peux dire que le jeu est au "
    "premier plan avec saisie recente, sans affirmer l'identite du joueur. Si le jeu a focus=non, "
    "il est seulement visible : la saisie va a la fenetre focus=oui.",
    "C_focus_dabord": CONSIGNE_BASE + CONSIGNE_JEU,  # retenue (4/4 le 18/09)
    "D_sans_regle_jeu": CONSIGNE_BASE,
}

Q_JOUE = "Est-ce que je suis en train de jouer en ce moment ?"
Q_CAMP = "Est-ce que je joue (clavier/souris) et quelle fenetre de jeu est visible ?"


def raw(exe, title, mon, hwnd):
    return {"exe": exe, "title": title, "pid": hwnd, "monitor_index": mon, "monitor_count": 2,
            "left": 0, "top": 0, "right": 800, "bottom": 600, "center_x": 400, "center_y": 300,
            "hwnd": hwnd}


def scenario(jeu_focus: bool, question: str) -> str:
    now = int(time.time() * 1000)
    evs = [sample_input_activity(idle_reader=lambda: 2000), adapt_texte(question, ts_wall_ms=now)]
    if jeu_focus:
        evs.append(_event_from_raw(raw("GrandFantasia.exe", "Grand Fantasia Violet", 0, 2), cfg=DEFAULT_CONFIG, focus=True))
    else:
        evs.append(_event_from_raw(raw("Cursor.exe", "fuser.py - Fusion-Layer - Cursor", 0, 1), cfg=DEFAULT_CONFIG, focus=True))
        evs.append(_event_from_raw(raw("GrandFantasia.exe", "Grand Fantasia Violet", 1, 2), cfg=DEFAULT_CONFIG, focus=False))
    return fuse(evs, now_ms=now).packet.text


SCENARIOS = {
    "S1 jeu focus, q=joue ? (attendu: OUI)": scenario(True, Q_JOUE),
    "S1b jeu focus, q=campagne (attendu: OUI)": scenario(True, Q_CAMP),
    "S2 jeu HORS focus, q=joue ? (attendu: NON)": scenario(False, Q_JOUE),
    "S2b jeu HORS focus, q=campagne (attendu: NON)": scenario(False, Q_CAMP),
}

only = sys.argv[1:] or list(CANDIDATES)
for name in only:
    print(f"===== {name}")
    for sname, packet in SCENARIOS.items():
        reply, _ = _ollama_chat(packet, consigne=CANDIDATES[name])
        print(f"  {sname}\n     -> {reply.replace(chr(10), ' ')}")
