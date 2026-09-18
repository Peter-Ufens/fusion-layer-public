"""Package Fusion Layer."""

from .contract import (
    CONTRACT_EVENT,
    CONTRACT_PACKET,
    ContractError,
    ConflictTrace,
    FusionEvent,
    FusionPacket,
    build_observations_block,
    compare_ordinal,
)
from .fuser import FuseResult, fuse

__all__ = [
    "CONTRACT_EVENT",
    "CONTRACT_PACKET",
    "ContractError",
    "ConflictTrace",
    "FusionEvent",
    "FusionPacket",
    "FuseResult",
    "build_observations_block",
    "compare_ordinal",
    "fuse",
]
