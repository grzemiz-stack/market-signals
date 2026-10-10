"""Ochrona tekstu z literatury w docs/MAPA-ZALEZNOSCI.md.

Suma sha256 liczona z całego pliku PO WYCIĘCIU bloku generowanego (między <!-- STATUS:START --> i <!-- STATUS:END -->,
włącznie ze znacznikami i jednym znakiem nowej linii przed blokiem). Wzorzec w tools/mapa_tekst.sha256.
Zmiana tekstu mapy = świadoma aktualizacja wzorca: python3 tools/check_mapa.py --update (z uzasadnieniem w commicie).
"""

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPA = ROOT / "docs" / "MAPA-ZALEZNOSCI.md"
REF = ROOT / "tools" / "mapa_tekst.sha256"
BLOCK = re.compile(r"\n?<!-- STATUS:START -->.*?<!-- STATUS:END -->\n?", re.S)


def text_hash() -> str:
    return hashlib.sha256(BLOCK.sub("", MAPA.read_text(encoding="utf-8")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    h = text_hash()
    if "--update" in sys.argv:
        REF.write_text(h + "\n")
        print("zaktualizowano wzorzec:", h)
        sys.exit(0)
    want = REF.read_text().strip()
    if h != want:
        print(f"MAPA: tekst poza blokiem statusów zmieniony ({h} != {want})")
        sys.exit(1)
    print("mapa: tekst z literatury nietknięty")
