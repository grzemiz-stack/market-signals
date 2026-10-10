"""E2 (etap 4N): odtworzenie lokalnego wzorca ref/e2_wgc_gold.csv z indeksu ref/e2_wgc_index.csv.

Kopia publiczna NIE zawiera cytatów z WGC Gold Market Commentary (warunki gold.org: tylko użytek osobisty). Indeks ma
miesiąc, URL, kod i położenie zdania w tekście strony (start, długość) + SHA-256 zdania. Strony zapisujesz sam do
data/raw/wgc_gmc/gold-market-commentary-<miesiąc>-<rok>.html (np. przeglądarką: „Zapisz jako… HTML”), potem:

uv run src/e2_wgc_restore.py      # -> ref/e2_wgc_gold.csv (gitignore); błąd, gdy hash się nie zgadza (inna wersja strony)
"""

from __future__ import annotations

import hashlib
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "ref" / "e2_wgc_index.csv"
OUT = ROOT / "ref" / "e2_wgc_gold.csv"
RAW = ROOT / "data" / "raw" / "wgc_gmc"


BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "tr", "table", "section",
         "article", "header", "footer", "figure", "figcaption", "blockquote", "nav", "main", "aside"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in ("script", "style")
        if tag in BLOCK:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        self.skip -= tag in ("script", "style") and self.skip > 0
        if tag in BLOCK:
            self.parts.append(" ")

    def handle_data(self, d):
        if not self.skip:
            self.parts.append(d)


def page_text(raw: str) -> str:
    """Tekst strony: bez znaczników, skryptów i stylów; spacja tylko na granicy bloków (akapit, lista, tabela…), nie wokół
    znaczników w zdaniu (link, przypis); encje rozwinięte; białe znaki zwinięte do jednej spacji."""
    p = _Text()
    p.feed(raw)
    return re.sub(r"\s+", " ", html.unescape("".join(p.parts))).strip()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def page_file(url: str) -> Path:
    return RAW / (url.rstrip("/").rsplit("/", 1)[1] + ".html")


def restore(index: pd.DataFrame) -> pd.DataFrame:
    out = []
    for r in index.itertuples():
        quote = None
        if pd.notna(r.start):
            text = page_text(page_file(r.url).read_text(errors="replace"))
            quote = text[int(r.start):int(r.start) + int(r.length)]
            if sha(quote) != r.sha256:
                raise SystemExit(f"{r.miesiac}: zdanie nie pasuje do hasha — inna wersja strony {r.url}")
        out.append({"miesiac": r.miesiac, "url": r.url, "cytat": quote, "kod": r.kod, "wlaczony": r.wlaczony,
                    "uwaga": r.uwaga, "konwencja": r.konwencja})
    return pd.DataFrame(out)


def main() -> int:
    g = restore(pd.read_csv(INDEX, comment="#"))
    OUT.write_text("# Odtworzone lokalnie z ref/e2_wgc_index.csv (src/e2_wgc_restore.py). Do użytku osobistego (warunki "
                   "gold.org) — nie publikować.\n" + g.to_csv(index=False))
    print(f"{OUT}: {int(g['cytat'].notna().sum())} cytatów, {len(g)} wierszy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
