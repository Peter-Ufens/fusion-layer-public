"""Capteur fenetre active / jeux hors focus + R1 game."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.adapters.ouie_stt import adapt_ouie_stt  # noqa: E402
from fusion_layer.adapters.vision_screen import adapt_vision_screen  # noqa: E402
from fusion_layer.capteurs import fenetre_active  # noqa: E402
from fusion_layer.capteurs.fenetre_active import (  # noqa: E402
    sample_foreground_window,
    sample_screen_context,
)
from fusion_layer.fuser import fuse  # noqa: E402

RAW = Path(__file__).parent / "fixtures" / "raw"


def test_garde_fou_pas_de_capture_pixels():
    src = Path(fenetre_active.__file__).read_text(encoding="utf-8")
    code = src.split('"""', 2)[2]
    for interdit in ("BitBlt", "PrintWindow", "mss", "PIL", "pyautogui", "GetAsyncKeyState"):
        assert interdit not in code


def test_whatsapp_root_est_refuse_comme_chat():
    """WhatsApp.Root.exe (Store) doit etre chat, pas unknown/browser (Bob L4)."""
    from fusion_layer.capteurs.fenetre_active import _category_for_exe

    assert _category_for_exe("WhatsApp.Root.exe") == "chat"
    assert _category_for_exe("WhatsApp.exe") == "chat"


def test_sample_foreground_reader_injecte():
    ev = sample_foreground_window(
        reader=lambda: {
            "exe": "GrandFantasia.exe",
            "title": "Grand Fantasia Violet",
            "pid": 1,
            "monitor_index": 1,
            "monitor_count": 2,
            "left": 2600,
            "top": 200,
            "right": 3400,
            "bottom": 900,
            "center_x": 3000,
            "center_y": 550,
            "hwnd": 42,
        }
    )
    assert ev.facets["category"] == "game"
    assert "moniteur_index=1" in (ev.text or "")
    assert "ecrans_detectes=2" in (ev.text or "")


def test_fuse_garde_deux_vision_screen_exes_differents():
    cursor = adapt_vision_screen(
        {
            "type": "screen.context",
            "payload": {
                "t_wall_ms": 1000,
                "confidence": "high",
                "process": {"exe_name": "Cursor.exe", "category": "agent"},
                "document": {},
                "window": {"title": "Fusion"},
            },
        }
    )
    cursor = replace(cursor, facets={**(cursor.facets or {}), "exe": "Cursor.exe"}).validate()
    game = sample_foreground_window(
        reader=lambda: {
            "exe": "GrandFantasia.exe",
            "title": "Grand Fantasia Violet",
            "pid": 2,
            "monitor_index": 1,
            "monitor_count": 2,
            "left": 0,
            "top": 0,
            "right": 100,
            "bottom": 100,
            "center_x": 50,
            "center_y": 50,
            "hwnd": 99,
        }
    )
    game = replace(game, ts_wall_ms=1000).validate()
    result = fuse([cursor, game], now_ms=2000)
    vision = [e for e in result.observation_events if e.modality == "vision_screen"]
    assert len(vision) == 2


def test_r1_declenche_aussi_sur_categorie_game():
    line = json.loads((RAW / "ouie_stt_autre.jsonl").read_text(encoding="utf-8").splitlines()[0])
    speech = adapt_ouie_stt(line)
    game = adapt_vision_screen(
        {
            "type": "screen.context",
            "payload": {
                "t_wall_ms": speech.ts_wall_ms,
                "confidence": "high",
                "process": {"exe_name": "GrandFantasia.exe", "category": "game"},
                "document": {},
                "window": {"title": "GF"},
            },
        }
    )
    result = fuse([speech, game], now_ms=speech.ts_wall_ms + 1000)
    assert any(c.rule == "R1" for c in result.conflicts)


@pytest.mark.skipif(sys.platform != "win32", reason="Win32")
def test_lecture_reelle_fenetre_ou_jeux():
    events = sample_screen_context()
    assert isinstance(events, list)
    assert len(events) >= 1
