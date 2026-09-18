"""Tests probes + CLI legers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.capteurs.reseau import list_up_links, sample_network
from fusion_layer.cli import main
from fusion_layer.probes.web_screen import screen_event_from_web


def _no_network(_addr, _timeout):
    """Echec simule : aucune ouverture reelle, verdict coupe."""
    raise OSError("offline simule")


def test_list_up_links_non_vide_sur_poste(monkeypatch):
    from fusion_layer.capteurs import reseau

    # pas de UDP/TCP reel : connect + route simules
    monkeypatch.setattr(reseau, "active_interface", lambda _h, _p: "Wi-Fi")
    links = list_up_links()
    assert isinstance(links, list)
    ev = sample_network(connect=_no_network, measure_activity=False)
    assert "lien=wifi" in (ev.text or "")
    assert "internet: latence_ms=" in (ev.text or "")
    assert "verdict=coupe" in (ev.text or "")


def test_screen_event_from_youtube():
    ev = screen_event_from_web(
        url="https://www.youtube.com/watch?v=aqz-KE-bpKQ",
        title="Big Buck Bunny",
        ts_wall_ms=1_700_000_000_000,
    )
    assert ev.modality == "vision_screen"
    assert "host=www.youtube.com" in (ev.text or "")
    assert "categorie=media" in (ev.text or "")
    assert "titre=Big Buck Bunny" in (ev.text or "")


def test_cli_network_exit_0(monkeypatch):
    from fusion_layer.capteurs import reseau

    monkeypatch.setattr(reseau, "_default_connect", _no_network)
    monkeypatch.setattr(reseau, "active_interface", lambda _h, _p: "Wi-Fi")
    assert main(["network"]) == 0


def test_cli_fuse_fixtures_exit_0():
    assert main(["fuse-fixtures"]) == 0
