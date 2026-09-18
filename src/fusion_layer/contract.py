"""Contrat fusion-layer/event@1 et packet@1 (ADR-0003).

Horloge d'alignement : ts_wall_ms uniquement.
Confiances : ordinal + brut typé, jamais comparer deux bruts entre modalités.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

CONTRACT_EVENT = "fusion-layer/event@1"
CONTRACT_PACKET = "fusion-layer/packet@1"

MODALITIES = frozenset(
    {
        "text",
        "speech",
        "audio_scene",
        "audio_pc",
        "vision_screen",
        "vision_webcam",
        "network",
        "memory",
        "input_activity",  # clavier / souris : presence au PC (ADR-0006)
    }
)
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low", "unknown"})
KINDS = frozenset({"ponctuel", "etat"})
SPEAKER_ROLES = frozenset({"peter", "autre_voix", "inconnu"})

# Canon ASCII pour JSON / configs. L'adaptateur Ouïe accepte aussi "Lyla-Ouïe".
SOURCE_PROJECTS = frozenset(
    {
        "Lyla-App",
        "Lyla-Ouie",
        "Lyla-Vision",
        "Lyla-Memory",
        "Fusion-Layer",
    }
)

SOURCE_PROJECT_ALIASES = {
    "Lyla-Ouïe": "Lyla-Ouie",
    "Lyla-Ouie": "Lyla-Ouie",
}

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, "unknown": 0}


class ContractError(ValueError):
    """Event ou paquet invalide."""


@dataclass
class FusionEvent:
    modality: str
    source_project: str
    source_type: str
    ts_wall_ms: int
    ts_origin: str
    kind: str
    confidence: str
    id: str = ""
    v: int = 1
    valid_ms: int | None = None
    text: str | None = None
    text_null_reason: str | None = None
    confidence_raw: float | None = None
    confidence_kind: str | None = None
    speaker_role: str | None = None
    untrusted: bool = False
    # Metadonnees structurees posees par l'adaptateur (ex. {"category": "media"}).
    # Le fuseur arbitre dessus, jamais sur le texte capte. Pas envoyees au LLM.
    facets: dict[str, str] | None = None

    def normalize(self) -> FusionEvent:
        self.source_project = SOURCE_PROJECT_ALIASES.get(
            self.source_project, self.source_project
        )
        if not self.id:
            basis = (
                f"{self.source_project}|{self.ts_wall_ms}|"
                f"{self.text or ''}|{self.source_type}"
            )
            # hashlib et pas hash() : hash() change a chaque processus (PYTHONHASHSEED),
            # l'id doit etre le meme d'un lancement a l'autre pour relire une trace.
            digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
            self.id = f"evt_{digest}"
        return self

    def validate(self) -> FusionEvent:
        self.normalize()
        if self.v != 1:
            raise ContractError(f"v attendu 1, reçu {self.v}")
        if self.modality not in MODALITIES:
            raise ContractError(f"modality inconnue: {self.modality}")
        if self.source_project not in SOURCE_PROJECTS:
            raise ContractError(f"source_project inconnue: {self.source_project}")
        if not isinstance(self.ts_wall_ms, int) or self.ts_wall_ms <= 0:
            raise ContractError("ts_wall_ms doit être un epoch ms > 0")
        if not self.ts_origin:
            raise ContractError("ts_origin obligatoire")
        if self.kind not in KINDS:
            raise ContractError(f"kind inconnu: {self.kind}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ContractError(f"confidence inconnue: {self.confidence}")
        if self.text is None and not self.text_null_reason:
            raise ContractError("text null exige text_null_reason")
        if self.text is not None and self.text_null_reason:
            raise ContractError("text et text_null_reason sont exclusifs")
        if self.speaker_role is not None and self.speaker_role not in SPEAKER_ROLES:
            raise ContractError(f"speaker_role invalide: {self.speaker_role}")
        if self.confidence_raw is not None and self.confidence_kind is None:
            raise ContractError("confidence_raw exige confidence_kind")
        if self.facets is not None and not (
            isinstance(self.facets, dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in self.facets.items())
        ):
            raise ContractError("facets doit etre un dict str -> str")
        return self

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FusionEvent:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {k: v for k, v in data.items() if k in known}
        return cls(**payload).validate()


@dataclass
class ConflictTrace:
    rule: str
    event_ids: list[str]
    decision: str


@dataclass
class FusionPacket:
    text: str
    packet_id: str
    t_ms: int
    window_ms: int
    included: list[str] = field(default_factory=list)
    excluded: list[dict[str, str]] = field(default_factory=list)
    conflicts: list[ConflictTrace] = field(default_factory=list)
    v: int = 1
    contract: str = CONTRACT_PACKET

    def validate(self) -> FusionPacket:
        if self.v != 1:
            raise ContractError(f"packet v attendu 1, reçu {self.v}")
        if not self.text.strip():
            raise ContractError("packet.text vide")
        if not self.packet_id:
            raise ContractError("packet_id obligatoire")
        if self.window_ms <= 0:
            raise ContractError("window_ms doit être > 0")
        return self

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        d = asdict(self)
        return d


def compare_ordinal(a: str, b: str) -> int:
    """Compare deux niveaux ordinaux. Ne compare jamais confidence_raw."""
    return CONFIDENCE_RANK.get(a, 0) - CONFIDENCE_RANK.get(b, 0)


_CHEVRONS = str.maketrans({"<": "‹", ">": "›"})


def sanitize_for_packet(text: str) -> str:
    """Un texte capte ne doit ni fermer le bloc <observations> ni forger une ligne.

    Retours a la ligne aplatis (sinon « \\n- [text, speaker_role=peter] ... » se
    ferait passer pour Peter) et chevrons neutralises (sinon « </observations> »
    ferme le bloc et la suite est lue comme une consigne).
    """
    return " ".join(text.split()).translate(_CHEVRONS)


def build_observations_block(events: list[FusionEvent]) -> str:
    """Bloc <observations> pour le LLM (textes untrusted délimités)."""
    lines = ["<observations>"]
    for ev in events:
        ev.validate()
        if ev.text is None:
            reason = sanitize_for_packet(ev.text_null_reason or "")
            lines.append(f"- [{ev.modality}/{ev.kind}] (pas de texte: {reason})")
            continue
        role = f", speaker_role={ev.speaker_role}" if ev.speaker_role else ""
        trust = ", untrusted" if ev.untrusted else ""
        lines.append(
            f"- [{ev.modality}{role}{trust}] {sanitize_for_packet(ev.text)}"
        )
    lines.append("</observations>")
    return "\n".join(lines)
