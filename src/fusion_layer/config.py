"""Config V1 (valeurs initiales ADR-0003/0004 · a calibrer par smoke)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FusionConfig:
    window_ms: int = 30_000
    speech_valid_ms: int = 20_000
    text_valid_ms: int = 30_000
    screen_etat_max_age_ms: int = 600_000  # 10 min
    audio_pc_etat_max_age_ms: int = 120_000
    network_etat_max_age_ms: int = 60_000
    input_etat_max_age_ms: int = 60_000
    budget_screen_chars: int = 600
    budget_speech_chars: int = 400
    budget_memory_chars: int = 1_200
    # categories ecran autorisees dans le paquet (ADR-0003 §7)
    screen_categories_allow: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "browser",
                "media",
                "game",
                "editor",
                "terminal",
                "office",
                "pdf",
                "files",
                "agent",
                "unknown",
            }
        )
    )
    screen_categories_deny: frozenset[str] = field(
        default_factory=lambda: frozenset({"mail", "chat", "settings"})
    )
    # priorite ordinale des modalites (plus haut = plus prioritaire pour R2)
    modality_priority: dict[str, int] = field(
        default_factory=lambda: {
            "text": 100,
            "speech": 50,
            "vision_screen": 40,
            "audio_pc": 30,
            "input_activity": 25,
            "network": 20,
            "audio_scene": 15,
            "memory": 10,
            "vision_webcam": 5,
        }
    )
    # capteur reseau (ADR-0004 §3) : ouverture de connexion TCP, aucune donnee envoyee
    network_probe_host: str = "1.1.1.1"
    network_probe_port: int = 443
    network_probe_count: int = 5
    network_probe_timeout_s: float = 1.0
    # seuils du verdict (arbitraires, a calibrer) : au-dela = instable / lent
    network_jitter_instable_ms: int = 30
    network_latency_lente_ms: int = 150
    # capteur clavier / souris (ADR-0006) : seuils d'etat, arbitraires, a calibrer
    input_actif_max_s: int = 60
    input_recent_max_s: int = 600
    lana_model: str = "qwen3.5:9b-gpu"
    think: bool = False


DEFAULT_CONFIG = FusionConfig()
