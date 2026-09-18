"""Capteur d'activite clavier / souris : presence au PC (idee Peter 18/09 · ADR-0006).

Ce qu'il mesure : depuis combien de temps Windows n'a recu AUCUNE saisie,
clavier ou souris confondus. C'est l'API que Windows utilise lui-meme pour
l'ecran de veille (`GetLastInputInfo`).

Ce qu'il ne fait JAMAIS : aucune touche lue, aucun texte, aucune position de
souris, aucun crochet clavier (hook), aucun droit administrateur, aucune
boucle en arriere-plan. Ce n'est pas un enregistreur de frappe et il ne doit
jamais le devenir.

Limites honnetes :
  - clavier et souris sont confondus : les separer demanderait d'espionner
    les touches ;
  - une manette de jeu ne compte pas comme saisie pour Windows : pendant une
    partie a la manette, le capteur voit « pas de saisie » ;
  - presence au clavier != voix de Peter : ce capteur ne dit pas QUI parle.
"""
from __future__ import annotations

import ctypes
import sys
import time
from typing import Callable

from fusion_layer.config import DEFAULT_CONFIG, FusionConfig
from fusion_layer.contract import FusionEvent

IdleReader = Callable[[], "int | None"]


def idle_since(now_tick: int, last_input_tick: int) -> int:
    """Millisecondes depuis la derniere saisie. Les compteurs Windows tiennent sur
    32 bits et repartent de zero tous les ~49,7 jours : le masque gere le passage."""
    return (now_tick - last_input_tick) & 0xFFFFFFFF


def read_idle_ms() -> int | None:
    """Inactivite clavier / souris en ms, ou None hors Windows / si l'API refuse."""
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    class _LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetTickCount.restype = wintypes.DWORD
    return idle_since(kernel32.GetTickCount(), info.dwTime)


def etat_from_idle(idle_s: float, cfg: FusionConfig) -> str:
    """Etat decrit comme un fait (saisie ou pas), pas comme une interpretation :
    Peter peut regarder un film deux heures sans toucher au clavier."""
    if idle_s <= cfg.input_actif_max_s:
        return "actif"
    if idle_s <= cfg.input_recent_max_s:
        return "sans_saisie_recente"
    return "sans_saisie_longue"


def sample_input_activity(
    cfg: FusionConfig | None = None, *, idle_reader: IdleReader | None = None
) -> FusionEvent:
    cfg = cfg or DEFAULT_CONFIG
    idle = (idle_reader or read_idle_ms)()
    common = dict(
        modality="input_activity",
        source_project="Fusion-Layer",
        source_type="fusion/input-activity@1",
        ts_wall_ms=int(time.time() * 1000),
        ts_origin="wall_now",
        kind="etat",
        untrusted=False,
    )
    if idle is None:
        return FusionEvent(
            **common,
            text=None,
            text_null_reason="api_windows_indisponible",
            confidence="unknown",
        ).validate()
    idle_s = idle / 1000
    etat = etat_from_idle(idle_s, cfg)
    return FusionEvent(
        **common,
        # etiquette explicite (lecon F9 du capteur reseau) : le LLM ne doit pas
        # en deduire qui parle
        text=(
            f"clavier_souris: derniere_saisie_il_y_a_s={idle_s:.0f} etat={etat}"
            " (presence au PC, ne dit PAS qui parle)"
        ),
        confidence="high",
        facets={"etat": etat},
    ).validate()
