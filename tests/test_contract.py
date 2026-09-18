"""Tests du contrat fusion-layer/event@1 (ADR-0003)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.contract import (  # noqa: E402
    ContractError,
    FusionEvent,
    FusionPacket,
    build_observations_block,
    compare_ordinal,
)

FIX = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_alias_ouie_accent_normalise():
    ev = FusionEvent.from_dict(_load("speech_autre_voix.json"))
    assert ev.source_project == "Lyla-Ouie"
    assert ev.speaker_role == "autre_voix"
    assert ev.untrusted is True
    assert ev.confidence == "unknown"


def test_screen_etat_sans_valid_ms_ok():
    ev = FusionEvent.from_dict(_load("vision_screen_media.json"))
    assert ev.kind == "etat"
    assert ev.valid_ms is None
    assert ev.confidence_kind == "vision_level"


def test_reject_sans_horloge():
    data = _load("text_peter.json")
    data["ts_wall_ms"] = 0
    with pytest.raises(ContractError, match="ts_wall_ms"):
        FusionEvent.from_dict(data)


def test_reject_text_null_sans_raison():
    data = _load("network_unstable.json")
    data["text"] = None
    data["text_null_reason"] = None
    with pytest.raises(ContractError, match="text_null_reason"):
        FusionEvent.from_dict(data)


def test_ordinal_ne_compare_pas_les_bruts():
    assert compare_ordinal("high", "low") > 0
    assert compare_ordinal("unknown", "medium") < 0


def test_observations_block_marque_untrusted():
    events = [
        FusionEvent.from_dict(_load("vision_screen_media.json")),
        FusionEvent.from_dict(_load("speech_autre_voix.json")),
        FusionEvent.from_dict(_load("network_unstable.json")),
    ]
    block = build_observations_block(events)
    assert "<observations>" in block
    assert "untrusted" in block
    assert "autre_voix" in block
    assert "pirate" in block


def test_packet_minimal():
    pkt = FusionPacket(
        text="resume test",
        packet_id="pkt_test",
        t_ms=1726665603000,
        window_ms=30000,
        included=["fix_screen_media", "fix_network_unstable"],
    )
    d = pkt.to_dict()
    assert d["contract"] == "fusion-layer/packet@1"
    assert d["included"][0] == "fix_screen_media"


def test_r1_conflit_voix_film_detectable():
    """R1 (Bob) : autre_voix + ecran media => phrase non-demande Peter."""
    speech = FusionEvent.from_dict(_load("speech_autre_voix.json"))
    screen = FusionEvent.from_dict(_load("vision_screen_media.json"))
    assert speech.speaker_role == "autre_voix"
    assert "categorie=media" in (screen.text or "")
    # Le fuseur n'existe pas encore : on fige la condition testable.
    r1_applies = speech.speaker_role in {"autre_voix", "inconnu"} and "categorie=media" in (
        screen.text or ""
    )
    assert r1_applies is True
