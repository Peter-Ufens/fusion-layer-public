"""Les scripts de preuve n'agissent que sur les fenetres qu'ils ont ouvertes (Bob 18/09)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="script Win32")


def _script():
    spec = importlib.util.spec_from_file_location(
        "preuve_externe_vision", ROOT / "scripts" / "preuve_externe_vision.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _w(hwnd: int, exe: str, title: str) -> dict:
    return {"hwnd": hwnd, "exe": exe, "title": title}


# Fenetres de Peter deja ouvertes AVANT le test, dont les titres contiennent les mots vises
AVANT = [
    _w(1, "brave.exe", "Fil d'actualite | LinkedIn - Brave"),
    _w(2, "Cursor.exe", "brouillon-post-linkedin.md - Agent-Communication - Cursor"),
    _w(3, "chrome.exe", "Big Buck Bunny - YouTube - Google Chrome"),
    _w(4, "msedgewebview2.exe", "LinkedIn"),  # app LinkedIn deja ouverte par Peter
]


def test_linkedin_ne_vise_que_la_fenetre_d_app_apparue():
    mod = _script()
    avant = {w["hwnd"] for w in AVANT}
    apres = AVANT + [
        _w(10, "msedgewebview2.exe", "Fil d'actualite | LinkedIn"),  # ouverte par le test
        _w(11, "brave.exe", "Messagerie | LinkedIn - Brave"),  # Peter ouvre un onglet pendant le test
    ]
    cibles = mod.nouvelles_fenetres(avant, apres, exes=mod.LINKEDIN_EXES, mot="linkedin")
    assert [w["hwnd"] for w in cibles] == [10]


def test_navigateur_ne_vise_que_la_fenetre_lancee():
    mod = _script()
    avant = {w["hwnd"] for w in AVANT}
    apres = AVANT + [_w(20, "chrome.exe", "Big Buck Bunny - YouTube - Google Chrome")]
    cibles = mod.nouvelles_fenetres(avant, apres, exes=frozenset({"chrome"}))
    assert [w["hwnd"] for w in cibles] == [20]  # jamais le Chrome (3) ni le Brave (1) de Peter


def test_plus_de_fermeture_ou_focus_par_simple_titre():
    source = (ROOT / "scripts" / "preuve_externe_vision.py").read_text(encoding="utf-8")
    assert "_close_windows_by_title" not in source
    assert "_focus_titles_matching" not in source
