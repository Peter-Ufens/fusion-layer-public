"""Capteur fenetre (poste Windows) · ecran sans Lyla-Vision.

1) Fenetre au premier plan (GetForegroundWindow)
2) En plus : fenetres suivies visibles (EnumWindows), meme hors focus :
   jeux connus, navigateurs, IDE/agents (Cursor, Claude)
   (multi-ecran : le jeu peut etre actif sous les doigts pendant que Cursor a le focus)

Pas de pixels, pas d'OCR, pas de touches.
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from typing import Callable

from fusion_layer.config import DEFAULT_CONFIG, FusionConfig
from fusion_layer.contract import FusionEvent

# Nom EXACT de l'executable (sans .exe, minuscules) -> categorie. Pas de
# sous-chaine : « steam » classait steamwebhelper (navigateur interne de Steam)
# en jeu, et « code » tout executable contenant ces lettres en editeur.
_EXE_CATEGORY = {
    "grandfantasia": "game",
    "steam": "game",
    "epicgameslauncher": "game",
    "chrome": "browser",
    "msedge": "browser",
    "brave": "browser",
    "firefox": "browser",
    "linkedin": "office",
    "code": "editor",
    "cursor": "agent",
    "claude": "agent",
    "devenv": "editor",
    "notepad": "editor",
    "spotify": "media",
    "vlc": "media",
    # messageries et mails : categories refusees (vie privee, ADR-0003 §7)
    "discord": "chat",
    "telegram": "chat",
    "whatsapp": "chat",
    "whatsapp.root": "chat",  # exe Windows Store / desktop observe (Bob L4)
    "signal": "chat",
    "ms-teams": "chat",
    "outlook": "mail",
    "olk": "mail",  # nouvel Outlook
    "thunderbird": "mail",
    "windowsterminal": "terminal",
    "cmd": "terminal",
    "powershell": "terminal",
    "pwsh": "terminal",
    "explorer": "files",
}

# Fenetres a suivre meme hors focus (multi-ecran) : nom exact d'executable.
_GAME_EXES = frozenset({"grandfantasia"})
_BROWSER_EXES = frozenset({"brave", "chrome", "msedge", "firefox"})
# IDE / agents : pour valider un objectif « concentre-toi sur Cursor » hors focus.
_AGENT_EXES = frozenset({"cursor", "claude"})
_SIDE_EXES = _GAME_EXES | _BROWSER_EXES | _AGENT_EXES


def _exe_key(exe: str) -> str:
    low = (exe or "").strip().lower()
    return low[:-4] if low.endswith(".exe") else low


def _category_for_exe(exe: str) -> str:
    return _EXE_CATEGORY.get(_exe_key(exe), "unknown")


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def _monitors() -> list[tuple[int, int, int, int, bool]]:
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    out: list[tuple[int, int, int, int, bool]] = []

    def _cb(hmon, _hdc, _lprc, _data):
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            primary = bool(mi.dwFlags & 1)
            out.append((r.left, r.top, r.right, r.bottom, primary))
        return 1

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(_RECT),
        wintypes.LPARAM,
    )
    user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_cb), 0)
    return out


def _exe_for_pid(pid: int) -> str:
    kernel32 = ctypes.windll.kernel32
    hproc = kernel32.OpenProcess(0x1000, False, pid)
    if not hproc:
        return ""
    try:
        size = wintypes.DWORD(520)
        name_buf = ctypes.create_unicode_buffer(520)
        if kernel32.QueryFullProcessImageNameW(hproc, 0, name_buf, ctypes.byref(size)):
            path = name_buf.value or ""
            return path.rsplit("\\", 1)[-1]
    finally:
        kernel32.CloseHandle(hproc)
    return ""


def _window_info(hwnd: int) -> dict[str, str | int] | None:
    user32 = ctypes.windll.user32
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return None
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return None
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value or ""
    if not title.strip():
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    exe = _exe_for_pid(int(pid.value))
    rect = _RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    # ignorer fenetres minimisees / hors ecran absurdes
    if rect.right - rect.left < 50 or rect.bottom - rect.top < 50:
        return None
    cx = (rect.left + rect.right) // 2
    cy = (rect.top + rect.bottom) // 2
    mons = _monitors()
    monitor_index = -1
    for i, (l, t, r, b, _p) in enumerate(mons):
        if l <= cx < r and t <= cy < b:
            monitor_index = i
            break
    return {
        "exe": exe or "unknown",
        "title": title[:200],
        "pid": int(pid.value),
        "monitor_index": int(monitor_index),
        "monitor_count": len(mons),
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "center_x": int(cx),
        "center_y": int(cy),
        "hwnd": int(hwnd),
    }


def read_foreground() -> dict[str, str | int] | None:
    if sys.platform != "win32":
        return None
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    return _window_info(hwnd)


def find_side_windows() -> list[dict[str, str | int]]:
    """Fenetres visibles jeux/navigateurs suivis (hors focus OK, multi-ecran)."""
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    found: list[dict[str, str | int]] = []

    def _enum(hwnd, _lparam):
        info = _window_info(hwnd)
        if info and _exe_key(str(info.get("exe") or "")) in _SIDE_EXES:
            found.append(info)
        return 1

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(_enum), 0)
    return found


def find_game_windows() -> list[dict[str, str | int]]:
    """Compat : sous-ensemble jeux de find_side_windows()."""
    return [
        w
        for w in find_side_windows()
        if _exe_key(str(w.get("exe") or "")) in _GAME_EXES
    ]


ForegroundReader = Callable[[], dict[str, str | int] | None]


def _event_from_raw(
    raw: dict[str, str | int],
    *,
    cfg: FusionConfig,
    focus: bool,
) -> FusionEvent:
    common = dict(
        modality="vision_screen",
        source_project="Fusion-Layer",
        source_type="fusion/foreground-window@1" if focus else "fusion/side-window@1",
        ts_wall_ms=int(time.time() * 1000),
        ts_origin="wall_now",
        kind="etat",
        untrusted=True,
    )
    exe = str(raw.get("exe") or "unknown")
    title = str(raw.get("title") or "")
    cat = _category_for_exe(exe)
    # App Store LinkedIn tourne souvent sous msedgewebview2 : le titre porte LinkedIn
    if cat == "unknown" and "linkedin" in title.lower():
        cat = "office"
    # meme regle que l'adaptateur ecran : refus explicite, puis liste blanche
    if cat in cfg.screen_categories_deny or (
        cfg.screen_categories_allow and cat not in cfg.screen_categories_allow
    ):
        return FusionEvent(
            **common,
            text=None,
            text_null_reason=f"screen_category_denied:{cat}",
            confidence="high",
            facets={"category": cat, "denied": "true"},
        ).validate()

    mon_i = raw.get("monitor_index", -1)
    mon_n = raw.get("monitor_count", 0)
    if focus:
        focus_s = "focus=oui"
    elif cat == "browser":
        focus_s = "focus=non (navigateur visible hors premier plan)"
    elif cat == "game":
        focus_s = "focus=non (jeu visible hors premier plan)"
    elif cat == "agent":
        focus_s = "focus=non (IDE/agent visible hors premier plan)"
    else:
        focus_s = "focus=non (fenetre suivie hors premier plan)"
    # etiquette explicite : moniteur_index=0 est le 1er ecran, PAS une absence
    # Contenu = titre de fenetre (pas OCR / pas pixels) : c'est ce que Fusion « lit ».
    text = (
        f"app={exe} categorie={cat} titre={title} "
        f"moniteur_index={mon_i} ecrans_detectes={mon_n} "
        f"centre_px=({raw.get('center_x')},{raw.get('center_y')}) "
        f"{focus_s} (contenu=titre fenetre Windows, PAS de capture pixels ni OCR)"
    )
    if len(text) > cfg.budget_screen_chars:
        text = text[: cfg.budget_screen_chars - 15].rstrip() + " …[tronque]"
    return FusionEvent(
        **common,
        text=text,
        confidence="high",
        facets={
            "category": cat,
            "exe": exe,
            "monitor_index": str(mon_i),
            "monitor_count": str(mon_n),
            "focus": "yes" if focus else "no",
        },
    ).validate()


def sample_foreground_window(
    cfg: FusionConfig | None = None, *, reader: ForegroundReader | None = None
) -> FusionEvent:
    """Premier plan uniquement."""
    cfg = cfg or DEFAULT_CONFIG
    raw = (reader or read_foreground)()
    if raw is None:
        return FusionEvent(
            modality="vision_screen",
            source_project="Fusion-Layer",
            source_type="fusion/foreground-window@1",
            ts_wall_ms=int(time.time() * 1000),
            ts_origin="wall_now",
            kind="etat",
            text=None,
            text_null_reason="api_windows_indisponible",
            confidence="unknown",
            untrusted=True,
        ).validate()
    return _event_from_raw(raw, cfg=cfg, focus=True)


def sample_screen_context(cfg: FusionConfig | None = None) -> list[FusionEvent]:
    """Premier plan + jeux/navigateurs/IDE suivis hors focus (multi-ecran).

    Ex. Grand Fantasia ecran 0 + Brave + Cursor ecran 1, meme si le focus est sur le jeu.
    """
    cfg = cfg or DEFAULT_CONFIG
    events: list[FusionEvent] = []
    fg = read_foreground()
    fg_hwnd = int(fg["hwnd"]) if fg and "hwnd" in fg else None
    if fg:
        events.append(_event_from_raw(fg, cfg=cfg, focus=True))

    for side in find_side_windows():
        if fg_hwnd is not None and int(side.get("hwnd") or 0) == fg_hwnd:
            continue  # deja couvert
        events.append(_event_from_raw(side, cfg=cfg, focus=False))
    return events
