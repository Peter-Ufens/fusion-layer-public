"""Capteur reseau interne (ADR-0004 · ADR-0005) · lecture seule systeme.

Ce qu'il mesure (ADR-0004 §3) :
  - le lien qui porte VRAIMENT Internet (celui de la route par defaut), pas un
    ordre de preference sur les noms d'interfaces ;
  - latence, gigue et pertes vers une cible Internet reglable ;
  - l'activite du moment (debit recu / envoye), donnee comme une activite et
    jamais comme une qualite : un PC au repos a peu de trafic et une bonne ligne.

Ce qu'il ne fait pas : aucune capture de paquets, aucune liste de sites ou de
connexions, aucune adresse IP dans le texte, aucun droit administrateur.

Methode de latence : duree d'ouverture d'une connexion TCP (poignee de main,
aucune donnee applicative envoyee, connexion fermee aussitot). Pas d'ICMP :
pas de droits requis, et pas de sortie de `ping` a decoder selon la langue.
"""
from __future__ import annotations

import socket
import statistics
import time
from typing import Any, Callable

from fusion_layer.config import DEFAULT_CONFIG, FusionConfig
from fusion_layer.contract import FusionEvent

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore

Connector = Callable[[tuple[str, int], float], None]


def _classify_if_name(name: str) -> str:
    low = name.lower()
    # virtuel avant ethernet : "vEthernet" contient "ethernet"
    if "vethernet" in low or "hyper-v" in low or "wsl" in low or "loopback" in low:
        return "virtuel"
    if "wi-fi" in low or "wlan" in low or "wifi" in low:
        return "wifi"
    if "ethernet" in low or low.startswith("eth"):
        return "ethernet"
    if "mobile" in low or "android" in low or "iphone" in low or "rndis" in low:
        return "partage_connexion"
    if "local area connection" in low:
        return "partage_connexion_possible"
    return "autre"


def list_up_links() -> list[dict[str, str]]:
    """Interfaces UP (sans IP dans le texte)."""
    if psutil is None:
        return []
    out: list[dict[str, str]] = []
    try:
        stats = psutil.net_if_stats()
    except Exception:
        return []
    for name, st in stats.items():
        if not st.isup:
            continue
        kind = _classify_if_name(name)
        out.append({"name": name, "kind": kind, "speed_mbps": str(getattr(st, "speed", 0) or 0)})
    return out


def active_interface(host: str, port: int) -> str | None:
    """Nom de l'interface qui porte la route vers `host`.

    Un socket UDP « connecte » ne transmet rien : il fait seulement choisir la
    route par le systeme. On lit l'adresse locale retenue et on retrouve
    l'interface qui la porte. L'adresse ne sort pas de cette fonction.
    """
    if psutil is None:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((host, port))
            local_ip = s.getsockname()[0]
        for name, addrs in psutil.net_if_addrs().items():
            if any(a.address == local_ip for a in addrs):
                return name
    except OSError:
        return None
    return None


def _default_connect(addr: tuple[str, int], timeout: float) -> None:
    with socket.create_connection(addr, timeout=timeout):
        pass


def probe_tcp(
    host: str, port: int, count: int, timeout_s: float, connect: Connector | None = None
) -> list[float | None]:
    """Duree (ms) de chaque ouverture de connexion, None si echec ou delai depasse."""
    connect = connect or _default_connect
    out: list[float | None] = []
    for _ in range(count):
        t0 = time.perf_counter()
        try:
            connect((host, port), timeout_s)
        except OSError:
            out.append(None)
            continue
        out.append((time.perf_counter() - t0) * 1000)
    return out


def summarize_probe(rtts: list[float | None], cfg: FusionConfig) -> dict[str, Any]:
    ok = [r for r in rtts if r is not None]
    lost = len(rtts) - len(ok)
    latency = statistics.median(ok) if ok else None
    jitter = (
        statistics.mean(abs(b - a) for a, b in zip(ok, ok[1:])) if len(ok) >= 2 else None
    )
    if not ok:
        verdict = "coupe"
    elif lost or (jitter is not None and jitter > cfg.network_jitter_instable_ms):
        verdict = "instable"
    elif latency is not None and latency > cfg.network_latency_lente_ms:
        verdict = "lent"
    else:
        verdict = "stable"
    return {"n": len(rtts), "lost": lost, "latency_ms": latency, "jitter_ms": jitter, "verdict": verdict}


def _activity_kBps(window_s: float = 0.5) -> tuple[float, float] | None:
    if psutil is None:
        return None
    try:
        a = psutil.net_io_counters()
        time.sleep(window_s)
        b = psutil.net_io_counters()
    except Exception:
        return None
    down = max(0, b.bytes_recv - a.bytes_recv) / 1000 / window_s
    up = max(0, b.bytes_sent - a.bytes_sent) / 1000 / window_s
    return down, up


def _fmt(v: float | None) -> str:
    return "?" if v is None else f"{v:.0f}"


def sample_network(
    cfg: FusionConfig | None = None,
    *,
    connect: Connector | None = None,
    measure_activity: bool = True,
) -> FusionEvent:
    """Mesure reelle : lien actif + latence / gigue / pertes + activite."""
    cfg = cfg or DEFAULT_CONFIG
    host, port = cfg.network_probe_host, cfg.network_probe_port
    if_name = active_interface(host, port)
    kind = _classify_if_name(if_name) if if_name else "unknown"
    s = summarize_probe(
        probe_tcp(host, port, cfg.network_probe_count, cfg.network_probe_timeout_s, connect),
        cfg,
    )
    parts = [
        f"lien={kind}" + (f" ({if_name})" if if_name else ""),
        f"internet: latence_ms={_fmt(s['latency_ms'])} gigue_ms={_fmt(s['jitter_ms'])}"
        f" perte={s['lost']}/{s['n']} verdict={s['verdict']}",
    ]
    activity = _activity_kBps() if measure_activity else None
    if activity is not None:
        # Etiquette explicite : a l'essai du 18/09, le LLM a lu « activite recu=5 »
        # comme un manque de bande passante alors que rien ne se telechargeait.
        parts.append(
            f"trafic_du_moment_kBps: recu={activity[0]:.0f} envoye={activity[1]:.0f}"
            " (usage actuel du PC, PAS la capacite de la ligne)"
        )
    # La confiance porte sur la MESURE, pas sur la qualite de la ligne : 5 echecs
    # sur 5 sont un fait sur (« coupe »). Pas de probabilite inventee (ADR-0003 §2).
    confidence = "high" if if_name else "medium"
    return FusionEvent(
        modality="network",
        source_project="Fusion-Layer",
        source_type="fusion/network@1",
        ts_wall_ms=int(time.time() * 1000),
        ts_origin="wall_now",
        valid_ms=None,
        kind="etat",
        text=" · ".join(parts),
        confidence=confidence,
        untrusted=False,
        facets={"lien": kind, "verdict": s["verdict"]},
    ).validate()


def adapt_network_dict(raw: dict[str, Any], cfg: FusionConfig | None = None) -> FusionEvent:
    """Pour fixtures / tests hors ligne. La confiance est celle declaree par la fixture."""
    confidence = str(raw.get("confidence") or "unknown")
    facets = raw.get("facets") if isinstance(raw.get("facets"), dict) else None
    return FusionEvent(
        id=str(raw.get("id") or ""),
        modality="network",
        source_project="Fusion-Layer",
        source_type="fusion/network@1",
        ts_wall_ms=int(raw.get("ts_wall_ms") or int(time.time() * 1000)),
        ts_origin=str(raw.get("ts_origin") or "fixture"),
        valid_ms=None,
        kind="etat",
        text=str(raw.get("text") or "lien=unknown"),
        confidence=confidence,
        untrusted=False,
        facets=facets,
    ).validate()
