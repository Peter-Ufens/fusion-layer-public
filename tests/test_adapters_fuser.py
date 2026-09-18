"""Tests adaptateurs + fuseur R1."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.adapters.ouie_stt import adapt_ouie_stt, adapt_ouie_stt_jsonl
from fusion_layer.adapters.ouie_system import adapt_ouie_system_jsonl
from fusion_layer.adapters.texte import adapt_texte
from fusion_layer.adapters.vision_screen import adapt_vision_screen, adapt_vision_screen_jsonl
from fusion_layer.capteurs.reseau import adapt_network_dict, sample_network
from fusion_layer.contract import ContractError
from fusion_layer.fuser import fuse

RAW = Path(__file__).parent / "fixtures" / "raw"
# 2026-09-18T15:00:02+02:00 (aligne fixtures ISO)
NOW = 1789736402000


def test_adapt_stt_speaker_unknown_autre_ou_inconnu():
    line = json.loads((RAW / "ouie_stt_autre.jsonl").read_text(encoding="utf-8").splitlines()[0])
    ev = adapt_ouie_stt(line)
    assert ev.modality == "speech"
    assert ev.speaker_role == "inconnu"
    assert ev.untrusted is True
    assert ev.ts_origin == "ts_iso"


def test_adapt_vision_screen_media():
    evs = adapt_vision_screen_jsonl(RAW / "vision_screen_media.jsonl")
    assert len(evs) == 1
    assert evs[0].kind == "etat"
    assert "categorie=media" in (evs[0].text or "")
    assert evs[0].ts_origin == "payload.t_wall_ms"


def test_adapt_vision_mail_refuse():
    line = json.loads(
        (RAW / "vision_screen_mail_denied.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    with pytest.raises(ContractError, match="denied"):
        adapt_vision_screen(line)


def test_adapt_system_audio_pc():
    evs = adapt_ouie_system_jsonl(RAW / "ouie_system_playback.jsonl")
    assert len(evs) == 1
    assert evs[0].modality == "audio_pc"
    assert "media.playback" in (evs[0].text or "")


def test_fuse_r1_conflit_voix_film():
    speech = adapt_ouie_stt_jsonl(RAW / "ouie_stt_autre.jsonl")[0]
    screen = adapt_vision_screen_jsonl(RAW / "vision_screen_media.jsonl")[0]
    audio = adapt_ouie_system_jsonl(RAW / "ouie_system_playback.jsonl")[0]
    net = adapt_network_dict(
        {
            "text": "lien=partage_connexion verdict=instable perte=elevee",
            "ts_wall_ms": NOW - 500,
            "confidence": "medium",
            "facets": {"lien": "partage_connexion", "verdict": "instable"},
        }
    )
    question = adapt_texte(
        "Pourquoi la video saccade parfois ?",
        ts_wall_ms=NOW,
    )
    result = fuse([speech, screen, audio, net, question], now_ms=NOW)
    rules = [c.rule for c in result.conflicts]
    assert "R1" in rules
    assert "R2" in rules
    assert result.question == "Pourquoi la video saccade parfois ?"
    assert any("probablement_le_media" in (e.text or "") for e in result.observation_events)
    assert "pirate" in result.packet.text
    assert "<observations>" in result.packet.text
    # la question n'est pas obeie comme ordre systeme : elle est hors observations
    assert "Question de Peter:" in result.packet.text


def test_fuse_sans_r1_si_speaker_peter():
    line = json.loads((RAW / "ouie_stt_autre.jsonl").read_text(encoding="utf-8").splitlines()[0])
    line["speaker"] = "peter"
    line["speaker_confidence"] = 0.99
    speech = adapt_ouie_stt(line)
    screen = adapt_vision_screen_jsonl(RAW / "vision_screen_media.jsonl")[0]
    result = fuse([speech, screen], now_ms=NOW)
    assert not any(c.rule == "R1" for c in result.conflicts)


def test_sample_network_live(monkeypatch):
    # connexion + route simulees : les tests ne sortent pas sur le reseau
    from fusion_layer.capteurs import reseau

    monkeypatch.setattr(reseau, "active_interface", lambda _h, _p: "Ethernet")
    ev = sample_network(connect=lambda _a, _t: None, measure_activity=False)
    assert ev.modality == "network"
    assert ev.source_project == "Fusion-Layer"
    assert "lien=ethernet" in (ev.text or "")
    assert "verdict=stable" in (ev.text or "")  # connect no-op = RTT ~0
