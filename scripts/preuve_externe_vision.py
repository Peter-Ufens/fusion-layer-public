#!/usr/bin/env python3
"""Preuve vision navigateur EXTERNE + app LinkedIn (hors Cursor).

Protocole Peter :
  - ouvrir navigateur externe (profil jetable) → mesurer → FERMER (pas de video en boucle)
  - ouvrir app LinkedIn → mesurer → fermer
  - succes = la FENETRE vue (exe/titre), pas un mot dans nos metadonnees

Usage:
  set PYTHONPATH=src
  python scripts/preuve_externe_vision.py
"""
from __future__ import annotations

import argparse
import ctypes
import json
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fusion_layer.adapters.texte import adapt_texte  # noqa: E402
from fusion_layer.capteurs.clavier_souris import sample_input_activity  # noqa: E402
from fusion_layer.capteurs.fenetre_active import (  # noqa: E402
    _exe_key,
    _window_info,
    sample_screen_context,
)
from fusion_layer.capteurs.reseau import sample_network  # noqa: E402
from fusion_layer.cli import _ollama_chat  # noqa: E402
from fusion_layer.fuser import fuse  # noqa: E402
from fusion_layer.trace import write_trace  # noqa: E402

OUT = ROOT / "traces" / "preuve-externe-vision.jsonl"
YT = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
LINKEDIN_APPID = r"shell:AppsFolder\7EE7776C.LinkedInforWindows_w1wdnht996qgy!App"

user32 = ctypes.windll.user32


def _find_browser() -> Path | None:
    for p in (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
        Path.home() / r"AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe",
        Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ):
        if p.is_file():
            return p
    return None


# Programmes dont une fenetre LinkedIn (app Store) peut sortir. Jamais un
# navigateur ni un editeur : un onglet ou un fichier « linkedin » de Peter
# ne doit ni etre ramene au premier plan, ni recevoir WM_CLOSE (Bob 18/09).
LINKEDIN_EXES = frozenset(
    {"msedgewebview2", "applicationframehost", "linkedin", "linkedinforwindows", "linkedin.desktop"}
)


def _list_windows() -> list[dict]:
    """Fenetres visibles titrees : hwnd, pid, exe, title."""
    found: list[dict] = []

    def _enum(hwnd, _lp):
        info = _window_info(hwnd)
        if info:
            found.append(info)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(_enum), 0)
    return found


def nouvelles_fenetres(
    avant: set[int], fenetres: list[dict], *, exes: frozenset[str], mot: str | None = None
) -> list[dict]:
    """Fenetres APPARUES depuis `avant` (hwnd), du bon programme, titre contenant `mot`.

    Seules ces fenetres-la peuvent etre ramenees au premier plan ou fermees.
    Avant (Bob 18/09), tout titre contenant « brave », « chrome », « youtube » ou
    « linkedin » etait vise : les fenetres de Peter deja ouvertes aussi.
    """
    return [
        w
        for w in fenetres
        if int(w["hwnd"]) not in avant
        and _exe_key(str(w.get("exe") or "")) in exes
        and (mot is None or mot in str(w.get("title") or "").lower())
    ]


def _rafraichir(fenetres: list[dict]) -> list[dict]:
    """Relit chaque fenetre par son hwnd : le titre change apres ouverture
    (« Nouvel onglet » puis le titre de la video)."""
    return [info for w in fenetres if (info := _window_info(int(w["hwnd"])))]


def _focus(fenetres: list[dict]) -> list[str]:
    for w in fenetres:
        user32.ShowWindow(int(w["hwnd"]), 9)  # SW_RESTORE
        user32.SetForegroundWindow(int(w["hwnd"]))
    return [str(w["title"])[:120] for w in fenetres]


def _rmtree_patient(path: Path) -> bool:
    """Le navigateur tient encore ses fichiers juste apres taskkill : on reessaie."""
    for _ in range(10):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return True
        time.sleep(0.5)
    return False


def _fuse_snapshot(question: str, *, with_llm: bool) -> dict:
    now = int(time.time() * 1000)
    net = sample_network(measure_activity=False)
    act = sample_input_activity()
    wins = sample_screen_context()
    q = adapt_texte(question, ts_wall_ms=now)
    result = fuse([net, act, *wins, q], now_ms=now)
    row: dict = {
        "question": result.question,
        "conflicts": [c.rule for c in result.conflicts],
        "windows": [
            {
                "exe": (w.facets or {}).get("exe"),
                "category": (w.facets or {}).get("category"),
                "focus": (w.facets or {}).get("focus"),
                "text": (w.text or w.text_null_reason or "")[:240],
            }
            for w in wins
        ],
        "activity": act.text,
        "network_verdict": (net.facets or {}).get("verdict"),
        "packet_excerpt": result.packet.text[:700],
    }
    if with_llm:
        reply, proof = _ollama_chat(result.packet.text)
        row["llm_reply"] = reply
        row["llm_proof"] = proof
        write_trace(result, proof)
        if not (reply or "").strip():
            row["fail"] = "llm_vide"
    return row


def _kill_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )


def run_browser_external(*, url: str, with_llm: bool, watch_s: float) -> dict:
    browser = _find_browser()
    if browser is None:
        return {"ok": False, "fail": "aucun_navigateur_externe", "windows": []}

    profile = Path(tempfile.mkdtemp(prefix="fusion-browser-proof-"))
    cmd = [
        str(browser),
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        url,
    ]
    avant = {int(w["hwnd"]) for w in _list_windows()}
    browser_exe = frozenset({_exe_key(browser.name)})
    print(f"OPEN browser={browser.name} profile={profile}")
    proc = subprocess.Popen(cmd)
    deadline = time.time() + watch_s
    lancees: list[dict] = []
    focused: list[str] = []
    try:
        # on laisse la page charger tout le temps prevu, sans voler le focus
        while time.time() < deadline:
            if not lancees:
                lancees = nouvelles_fenetres(avant, _list_windows(), exes=browser_exe)
            time.sleep(0.8)
        lancees = _rafraichir(lancees)
        # une seule mise au premier plan, et seulement de la fenetre lancee
        focused = _focus(lancees)
        time.sleep(0.5)
        snap = _fuse_snapshot(
            "Quelle application est au premier plan maintenant ?",
            with_llm=with_llm,
        )
        snap["browser_launched"] = browser.name
        snap["url"] = url
        snap["titles_focused"] = focused
        # Preuve = LA fenetre lancee par ce test se retrouve dans le paquet.
        # Avant : n'importe quel « brave » suffisait, donc le Brave deja ouvert
        # de Peter validait la preuve sans que le navigateur lance soit vu.
        textes = " ".join(str(w.get("text") or "") for w in snap["windows"])
        seen = any(str(w["title"])[:60] in textes for w in lancees)
        snap["fenetre_lancee_vue"] = seen
        snap["fenetre_lancee_au_premier_plan"] = any(
            w.get("focus") == "yes" and any(str(x["title"])[:60] in str(w.get("text") or "") for x in lancees)
            for w in snap["windows"]
        )
        snap["ok"] = bool(seen) and "fail" not in snap
        if not seen:
            snap["fail"] = snap.get("fail") or "fenetre_lancee_non_vue_dans_le_paquet"
        return snap
    finally:
        print(f"CLOSE browser pid={proc.pid} (profil jetable uniquement)")
        _kill_tree(proc.pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        print("CLOSED ok" if _rmtree_patient(profile) else f"PROFIL RESTANT {profile}")


def _linkedin_process_names() -> set[str]:
    try:
        import psutil
    except ImportError:  # pragma: no cover
        return set()
    return {
        p.info["name"]
        for p in psutil.process_iter(["name"])
        if "linkedin" in (p.info["name"] or "").lower()
    }


def run_linkedin(*, with_llm: bool, watch_s: float) -> dict:
    avant = {int(w["hwnd"]) for w in _list_windows()}
    deja_lance = _linkedin_process_names()
    print(f"OPEN LinkedIn appid={LINKEDIN_APPID}")
    subprocess.Popen(["explorer.exe", LINKEDIN_APPID])
    deadline = time.time() + watch_s
    lancees: list[dict] = []
    focused: list[str] = []
    try:
        while time.time() < deadline and not lancees:
            lancees = nouvelles_fenetres(avant, _list_windows(), exes=LINKEDIN_EXES, mot="linkedin")
            time.sleep(0.8)
        time.sleep(1.5)  # le titre de l'app se remplit apres l'ouverture
        lancees = _rafraichir(lancees)
        focused = _focus(lancees)
        time.sleep(0.5)
        snap = _fuse_snapshot(
            "Quelle application est au premier plan maintenant ?",
            with_llm=with_llm,
        )
        snap["titles_focused"] = focused
        textes = " ".join(str(w.get("text") or "") for w in snap["windows"])
        seen = any(str(w["title"])[:60] in textes for w in lancees)
        snap["fenetre_lancee_vue"] = seen
        snap["ok"] = bool(seen) and "fail" not in snap
        if not seen:
            snap["fail"] = snap.get("fail") or "linkedin_lance_non_vu_dans_le_paquet"
        return snap
    finally:
        print("CLOSE LinkedIn (seulement ce que le test a ouvert)")
        if not deja_lance:
            # Peter n'avait pas l'app ouverte : on peut arreter ses processus.
            for im in ("LinkedIn.exe", "LinkedInforWindows.exe", "LinkedIn.Desktop.exe"):
                subprocess.run(
                    ["taskkill", "/IM", im, "/F"], capture_output=True, text=True, check=False
                )
        else:
            print(f"  app deja ouverte avant le test ({sorted(deja_lance)}) : processus laisses")
        _close_new_linkedin_windows(avant)
        print("CLOSE LinkedIn tente")


def _close_new_linkedin_windows(avant: set[int]) -> None:
    """WM_CLOSE seulement aux fenetres LinkedIn APPARUES pendant le test, sous un
    programme d'app (webview / cadre Store), jamais un navigateur ni un editeur.
    Avant (Bob 18/09) : toute fenetre dont le titre contenait « linkedin » (onglet
    Brave, fichier Cursor « post-linkedin.md »…) recevait WM_CLOSE."""
    WM_CLOSE = 0x0010
    for w in nouvelles_fenetres(avant, _list_windows(), exes=LINKEDIN_EXES, mot="linkedin"):
        user32.PostMessageW(int(w["hwnd"]), WM_CLOSE, 0, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=YT)
    ap.add_argument("--watch", type=float, default=12.0)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--skip-browser", action="store_true")
    ap.add_argument("--skip-linkedin", action="store_true")
    args = ap.parse_args()
    with_llm = not args.no_llm

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    results = []
    if not args.skip_browser:
        r = run_browser_external(url=args.url, with_llm=with_llm, watch_s=args.watch)
        results.append({"step": "browser_externe", **r})
        print(
            "BROWSER",
            "OK" if r.get("ok") else "FAIL",
            r.get("fail"),
            "windows=",
            r.get("windows"),
            "focused=",
            r.get("titles_focused"),
        )
        time.sleep(2)

    if not args.skip_linkedin:
        r = run_linkedin(with_llm=with_llm, watch_s=max(args.watch, 20.0))  # demarrage a froid > 14 s (Bob 18/09)
        results.append({"step": "linkedin_app", **r})
        print(
            "LINKEDIN",
            "OK" if r.get("ok") else "FAIL",
            r.get("fail"),
            "windows=",
            r.get("windows"),
            "focused=",
            r.get("titles_focused"),
        )

    with OUT.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    resume = {
        "steps": len(results),
        "ok": all(r.get("ok") for r in results),
        "fails": [r.get("fail") for r in results if not r.get("ok")],
        "fermeture_navigateur": "possible (profil jetable + taskkill arbre)",
        "fermeture_linkedin": "PostMessage WM_CLOSE + taskkill ImageName",
    }
    resume_path = ROOT / "traces" / "preuve-externe-vision-resume.json"
    resume_path.write_text(json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8")
    print("==== RESUME ====")
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    print(f"log={OUT}")
    print("limites_contexte=docs/LIMITES-CONTEXTE-LLM.md")
    return 0 if resume["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
