"""Capteur clavier / souris (ADR-0006) et regle R4."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer import cli  # noqa: E402
from fusion_layer.adapters.ouie_stt import adapt_ouie_stt  # noqa: E402
from fusion_layer.adapters.vision_screen import adapt_vision_screen  # noqa: E402
from fusion_layer.capteurs import clavier_souris  # noqa: E402
from fusion_layer.capteurs.clavier_souris import (  # noqa: E402
    etat_from_idle,
    idle_since,
    sample_input_activity,
)
from fusion_layer.config import FusionConfig  # noqa: E402
from fusion_layer.fuser import fuse  # noqa: E402

RAW = Path(__file__).parent / "fixtures" / "raw"


def _activity(idle_s: float):
    return sample_input_activity(idle_reader=lambda: int(idle_s * 1000))


def _speech_inconnue(now_ms: int):
    line = json.loads((RAW / "ouie_stt_autre.jsonl").read_text(encoding="utf-8").splitlines()[0])
    ev = adapt_ouie_stt(line)
    ev.ts_wall_ms = now_ms - 1000  # meme fenetre que l'activite, mesuree « maintenant »
    return ev


def _screen_media(now_ms: int):
    return adapt_vision_screen(
        {
            "type": "screen.context",
            "payload": {
                "t_wall_ms": now_ms - 2000,
                "confidence": "high",
                "process": {"exe_name": "chrome.exe", "category": "media"},
                "document": {"host": "youtube.com"},
                "window": {"title": "Film"},
            },
        }
    )


# --- garde-fou vie privee : ce capteur ne doit jamais devenir un enregistreur de frappe


def test_garde_fou_aucune_lecture_de_touche_dans_le_capteur():
    source = Path(clavier_souris.__file__).read_text(encoding="utf-8")
    code = source.split('"""', 2)[2]  # hors docstring de tete
    for interdit in ("SetWindowsHookEx", "GetAsyncKeyState", "GetKeyState", "pynput", "keyboard", "GetCursorPos"):
        assert interdit not in code, f"{interdit} interdit dans le capteur (ADR-0006)"


# --- mesure


def test_idle_since_gere_le_passage_a_zero_des_compteurs_windows():
    assert idle_since(5_000, 2_000) == 3_000
    assert idle_since(100, 0xFFFFFF00) == 356  # compteur reparti de zero entre-temps


@pytest.mark.parametrize(
    "idle_s,etat",
    [(0, "actif"), (60, "actif"), (61, "sans_saisie_recente"), (600, "sans_saisie_recente"), (601, "sans_saisie_longue")],
)
def test_etat(idle_s, etat):
    assert etat_from_idle(idle_s, FusionConfig()) == etat


def test_event_ne_contient_que_la_duree_et_l_etat():
    ev = _activity(12)
    assert ev.modality == "input_activity" and ev.kind == "etat"
    assert ev.text == (
        "clavier_souris: derniere_saisie_il_y_a_s=12 etat=actif"
        " (presence au PC, ne dit PAS qui parle)"
    )
    assert ev.facets == {"etat": "actif"}


def test_api_indisponible_dit_qu_elle_ne_sait_pas():
    ev = sample_input_activity(idle_reader=lambda: None)
    assert ev.text is None
    assert ev.text_null_reason == "api_windows_indisponible"
    assert ev.confidence == "unknown"


@pytest.mark.skipif(sys.platform != "win32", reason="API Windows")
def test_lecture_reelle_sur_le_poste():
    idle = clavier_souris.read_idle_ms()
    assert isinstance(idle, int) and idle >= 0


def test_cli_activite_exit_0():
    assert cli.main(["activite"]) == 0


# --- regle R4


def test_r4_voix_inconnue_sans_saisie_annotee_et_jamais_question():
    act = _activity(700)
    now = act.ts_wall_ms
    result = fuse([act, _speech_inconnue(now)], now_ms=now)
    assert any(c.rule == "R4" for c in result.conflicts)
    assert result.question is None
    assert any("[sans_saisie_clavier_souris R4]" in (e.text or "") for e in result.observation_events)


def test_r4_absente_si_peter_est_actif_mais_la_voix_ne_devient_pas_la_sienne():
    act = _activity(2)
    now = act.ts_wall_ms
    result = fuse([act, _speech_inconnue(now)], now_ms=now)
    assert not any(c.rule == "R4" for c in result.conflicts)
    # etre au clavier ne prouve pas qui parle
    assert result.question is None


def test_r1_et_r4_se_cumulent():
    act = _activity(900)
    now = act.ts_wall_ms
    result = fuse([act, _screen_media(now), _speech_inconnue(now)], now_ms=now)
    rules = {c.rule for c in result.conflicts}
    assert {"R1", "R4"} <= rules
    speech_obs = [e for e in result.observation_events if e.modality == "speech"][0]
    assert speech_obs.text.startswith("[probablement_le_media R1] [sans_saisie_clavier_souris R4]")
