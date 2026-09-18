#!/usr/bin/env python3
"""Exporte une arborescence vitrine (sans ops perso) vers un dossier cible.

Usage :
  python scripts/export_vitrine_publique.py D:\\tmp\\fusion-layer-public

Puis dans le dossier cible : git init / remote public / push (voir REPOS.md).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Chemins relatifs a copier (whitelist).
INCLUDE = [
    "src",
    "tests",
    "ADR",
    "docs",
    "scripts/preuve_ecran2_multimodal.py",
    "scripts/preuve_focus_objectif.py",
    "scripts/preuve_externe_vision.py",
    "scripts/campagne_preuve_v1.py",
    "scripts/banc_consigne_llm.py",
    "scripts/export_vitrine_publique.py",
    "presentations-gamma/README.md",
    "presentations-gamma/SOURCES.md",
    "presentations-gamma/LIMITES-GAMMA-GRATUIT.md",
    "CLOTURE.md",
    "REPOS.md",
    "README.md",
    ".gitignore",
    ".graphifyignore",
]

# Fichiers a ne jamais recopier meme s'ils matchent un dossier.
SKIP_NAMES = {
    "PERSONNES-SUIVI.md",
    "LIEN-VAULT.md",
}


def _copy_one(rel: str, dest_root: Path) -> None:
    src = ROOT / rel
    if not src.exists():
        print(f"SKIP missing {rel}")
        return
    dst = dest_root / rel
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                *SKIP_NAMES,
            ),
        )
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    print(f"OK {rel}")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    dest = Path(sys.argv[1]).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for rel in INCLUDE:
        _copy_one(rel, dest)
    # README vitrine leger : remplacer mention privee
    readme = dest / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        text = text.replace(
            "GitHub | **privé** · https://github.com/Peter-Ufens/Fusion-Layer",
            "GitHub | **public** · https://github.com/Peter-Ufens/fusion-layer · ops privé = Fusion-Layer",
        )
        text = text.replace("**Statut INDEX :** `actif`", "**Statut INDEX :** `cloture` (V1)")
        readme.write_text(text, encoding="utf-8")
    license_txt = dest / "LICENSE"
    if not license_txt.exists():
        license_txt.write_text(
            "MIT License\n\nCopyright (c) 2026 Peter UFENS\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
            'of this software and associated documentation files (the "Software"), to deal\n'
            "in the Software without restriction, including without limitation the rights\n"
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
            "copies of the Software, and to permit persons to whom the Software is\n"
            "furnished to do so, subject to the following conditions:\n\n"
            "The above copyright notice and this permission notice shall be included in all\n"
            "copies or substantial portions of the Software.\n\n"
            'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n'
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
            "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
            "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
            "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
            "SOFTWARE.\n",
            encoding="utf-8",
        )
    print(f"Export OK -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
