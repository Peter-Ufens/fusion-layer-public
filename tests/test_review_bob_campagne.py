"""Non-regression de la review Bob de la campagne V1 (18/09 soir)."""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.adapters.ouie_stt import adapt_ouie_stt  # noqa: E402
from fusion_layer.capteurs.fenetre_active import _category_for_exe, _event_from_raw  # noqa: E402
from fusion_layer.config import DEFAULT_CONFIG  # noqa: E402
from fusion_layer.fuser import fuse  # noqa: E402

RAW = Path(__file__).parent / "fixtures" / "raw"
NOW = 1789736402000


def _win(exe: str, title: str, *, focus: bool, ts: int = NOW, hwnd: int = 1):
    raw = {"exe": exe, "title": title, "pid": hwnd, "monitor_index": 0, "monitor_count": 2,
           "left": 0, "top": 0, "right": 800, "bottom": 600, "center_x": 400, "center_y": 300,
           "hwnd": hwnd}
    return replace(_event_from_raw(raw, cfg=DEFAULT_CONFIG, focus=focus), ts_wall_ms=ts).validate()


# B1 · un seul premier plan a la fois (l'ancien ne survit pas a cote du nouveau)


def test_un_seul_premier_plan_dans_le_paquet():
    old = _win("chrome.exe", "YouTube", focus=True, ts=NOW - 10_000, hwnd=1)
    new = _win("Cursor.exe", "fuser.py", focus=True, ts=NOW, hwnd=2)
    packet = fuse([old, new], now_ms=NOW).packet
    lignes_obs = [l for l in packet.text.splitlines() if l.startswith("- [vision_screen")]
    assert sum("focus=oui" in l for l in lignes_obs) == 1
    assert {"id": old.id, "reason": "remplace_par_etat_plus_recent"} in packet.excluded


# B8 · ligne de premier plan calculee par le code (le LLM se trompait avec 4 fenetres)


def test_ligne_premier_plan_quand_une_seule_fenetre_a_le_focus():
    chrome = _win("chrome.exe", "Big Buck Bunny - YouTube", focus=True, hwnd=1)
    jeu = _win("GrandFantasia.exe", "Grand Fantasia Violet", focus=False, hwnd=2)
    text = fuse([jeu, chrome], now_ms=NOW).packet.text
    assert "<premier_plan>Fenetre au premier plan (focus=oui, calcule par le code) : chrome.exe (categorie=browser)" in text
    # « <observations> » apparait aussi dans la consigne : on vise le debut du bloc
    assert text.index("<premier_plan>") < text.index("\n<observations>\n")


def test_pas_de_ligne_premier_plan_sans_focus_mesure():
    from fusion_layer.adapters.vision_screen import adapt_vision_screen

    # screen.context de Lyla-Vision : pas de facette focus -> on ne tranche pas
    ecran = adapt_vision_screen({"type": "screen.context", "payload": {
        "t_wall_ms": NOW, "confidence": "high", "process": {"exe_name": "chrome.exe", "category": "browser"},
        "document": {}, "window": {"title": "x"}}})
    assert "<premier_plan>" not in fuse([ecran], now_ms=NOW).packet.text


def test_jeu_hors_focus_reste_a_cote_du_premier_plan():
    cursor = _win("Cursor.exe", "fuser.py", focus=True, hwnd=1)
    jeu = _win("GrandFantasia.exe", "Grand Fantasia Violet", focus=False, hwnd=2)
    obs = fuse([cursor, jeu], now_ms=NOW).observation_events
    assert len([e for e in obs if e.modality == "vision_screen"]) == 2


def test_brave_hors_focus_reste_a_cote_du_jeu():
    """Ecran 2 Brave + ecran 0 jeu : les deux dans le paquet."""
    jeu = _win("GrandFantasia.exe", "Grand Fantasia Violet", focus=True, hwnd=1)
    brave = _win("brave.exe", "Ruines | Fandom - Brave", focus=False, hwnd=2)
    obs = fuse([jeu, brave], now_ms=NOW).observation_events
    vision = [e for e in obs if e.modality == "vision_screen"]
    assert len(vision) == 2
    texts = " ".join(e.text or "" for e in vision).lower()
    assert "brave" in texts and "grandfantasia" in texts


# B2 · categorie par nom EXACT d'executable, jamais par le titre


def test_categorie_par_nom_exact():
    assert _category_for_exe("GrandFantasia.exe") == "game"
    assert _category_for_exe("Code.exe") == "editor"
    assert _category_for_exe("steamwebhelper.exe") == "unknown"  # pas un jeu
    assert _category_for_exe("Encoder.exe") == "unknown"  # contient « code »


def test_titre_ne_fait_pas_d_une_fenetre_un_jeu():
    ev = _win("mystere.exe", "grandfantasia wiki - astuces", focus=True)
    assert ev.facets["category"] == "unknown"


# B3 · messageries et nouvel Outlook masques (titre = contenu prive)


def test_nouvel_outlook_et_messageries_masques():
    for exe in ("olk.exe", "WhatsApp.exe", "Telegram.exe", "ms-teams.exe"):
        ev = _win(exe, "Boite de reception - message prive", focus=True)
        assert ev.text is None, exe
        assert (ev.text_null_reason or "").startswith("screen_category_denied:"), exe


# B4 · R1 pendant un jeu : la voix peut etre un autre joueur, pas « le media »


def test_r1_etiquette_jeu():
    line = json.loads((RAW / "ouie_stt_autre.jsonl").read_text(encoding="utf-8").splitlines()[0])
    speech = adapt_ouie_stt(line)
    jeu = _win("GrandFantasia.exe", "Grand Fantasia Violet", focus=True, ts=speech.ts_wall_ms)
    result = fuse([speech, jeu], now_ms=speech.ts_wall_ms + 1000)
    speech_obs = [e for e in result.observation_events if e.modality == "speech"][0]
    assert speech_obs.text.startswith("[probablement_le_jeu_ou_un_joueur R1]")


# B6 · audio PC : la nature de la confiance vient d'Ouie, pas d'une etiquette en dur
# (ligne reelle Ouie B2 du 18/09 17:44, liste `apps` retiree)

OUIE_B2_REEL = {
    "type": "media.playback", "label": "unknown", "ts": "2026-09-18T17:44:43.975+02:00",
    "device": "pc", "channel": "system", "confidence": 0.3, "duration_s": 45.024,
    "meta": {"schema": "lyla-ouie/ambient-event@1", "phase": "B2", "confidence_kind": "heuristic_match",
             "rms_dbfs": -26.0, "speech_ratio": 0.0, "app": "GrandFantasia.exe"},
}


def test_audio_pc_reel_garde_la_nature_de_confiance_d_ouie():
    from fusion_layer.adapters.ouie_system import adapt_ouie_system

    ev = adapt_ouie_system(OUIE_B2_REEL)
    assert ev.modality == "audio_pc"
    assert ev.confidence_kind == "heuristic_match"
    assert ev.confidence == "low"
    assert "app_son=GrandFantasia.exe" in (ev.text or "")
    assert ev.facets == {"app": "GrandFantasia.exe"}


# B5 · la campagne n'envoie plus de reseau fabrique au LLM


def _campagne():
    spec = importlib.util.spec_from_file_location(
        "campagne_preuve_v1", ROOT / "scripts" / "campagne_preuve_v1.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_campagne_round_sans_mesure_reseau_sans_event_reseau(monkeypatch):
    camp = _campagne()

    def interdit(*_a, **_k):
        raise AssertionError("aucune mesure reseau attendue sur ce round")

    monkeypatch.setattr(camp, "sample_network", interdit)
    monkeypatch.setattr(camp, "sample_screen_context", lambda: [_win("Cursor.exe", "x", focus=True)])
    row = camp.one_round(1, with_llm=False, measure_net=False)
    assert row["network_verdict"] == "non_mesure"
    assert "[network]" not in row["packet_excerpt"]
    assert row["ok"] is True
