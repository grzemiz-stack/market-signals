"""Zasada „tylko lokalnie” (docs/DECISIONS.md 2026-10-07): sieć służy wyłącznie do POBIERANIA publicznych danych z listy
poniżej. Modele i agenci działają tylko na tym Macu (Ollama na 127.0.0.1), żadne dane nie wychodzą na zewnątrz.

Pilnuje tests/test_local_only.py: każdy host w kodzie (src/, tools/) musi być na tej liście albo lokalny; brak metod
wysyłających (POST/PUT/…) poza ms.llm do pętli zwrotnej; LLM tylko przez ms.llm.
Nowe źródło danych -> dopisz host tutaj (z komentarzem, co pobieramy).
"""

from __future__ import annotations

from urllib.parse import urlsplit

LOOPBACK = {"127.0.0.1", "localhost", "::1"}

# host -> co pobieramy (tylko GET publicznych danych)
DATA_SOURCES = {
    "api.stlouisfed.org": "FRED (makro, rynki)",
    "api.eia.gov": "EIA (ropa, zapasy)",
    "www.eia.doe.gov": "EIA: adres oryginału w ścieżce Wayback (4N, P4)",
    "web.archive.org": "Wayback: archiwum chronologii EIA (4N, P4)",
    "api.nbp.pl": "NBP kursy",
    "static.nbp.pl": "NBP stopy procentowe",
    "query2.finance.yahoo.com": "Yahoo Finance (ceny)",
    "stooq.com": "Stooq: metale dzienne (pobierane ręcznie, adres w opisie kolektora)",
    "data.binance.vision": "Binance archiwum świec",
    "fapi.binance.com": "Binance futures (OI, funding)",
    "api.bybit.com": "Bybit (OI, funding)",
    "www.deribit.com": "Deribit DVOL",
    "community-api.coinmetrics.io": "Coin Metrics community",
    "api.alternative.me": "Fear & Greed",
    "api.llama.fi": "DefiLlama: lista hacków (4N)",
    "data.gdeltproject.org": "GDELT",
    "www.matteoiacoviello.com": "GPR, TPU, AI-GPR (Iacoviello)",
    "s3-ap-northeast-1.amazonaws.com": "Binance Vision (archiwum świec, bucket S3)",
    "www.federalreserve.gov": "kalendarz FOMC",
    "www.frbsf.org": "FRBSF: niespodzianki polityki pieniężnej (4N)",
    "www.nhc.noaa.gov": "NOAA NHC: huragany (kalendarz zdarzeń)",
    "en.wikipedia.org": "Wikipedia: chronologia rynku ropy (wersje stałe, 4N)",
    "raw.githubusercontent.com": "GitHub raw: Coin Metrics CSV, szoki JK (Fed), szoki podaży ropy Känziga",
    "api.github.com": "GitHub API: ostatni commit repo Coin Metrics",
    "docs.google.com": "Google Sheets: publiczny arkusz źródła przyczyn (4N, eksport xlsx)",
    "drive.google.com": "Google Drive: szoki Baumeister–Hamilton (publiczny plik)",
    # 4N-live: kanały wiadomości (RSS; weryfikacja 2026-10-07 w docs/ETAP4N-LIVE-PLAN.md pkt 2)
    "www.rigzone.com": "Rigzone RSS (ropa; private, non-commercial)",
    "www.gold.org": "World Gold Council RSS (złoto)",
    "www.silverinstitute.org": "Silver Institute RSS (srebro)",
    "www.theblock.co": "The Block RSS (krypto; tylko czytnik)",
    "www.sec.gov": "SEC komunikaty RSS (User-Agent z kontaktem, D2)",
    "www.ecb.europa.eu": "EBC komunikaty RSS",
    "www.cftc.gov": "CFTC komunikaty i egzekucja RSS",
    "ofac.treasury.gov": "OFAC (sankcje) RSS",
    "www.bankofengland.co.uk": "Bank of England RSS",
    "www.bis.org": "BIS komunikaty RSS",
    "api.gdeltproject.org": "GDELT DOC 2.0 API (tytuły i linki wg tematów; limit 1 zapytanie / 5 s)",
    "www.hellenicshippingnews.com": "Hellenic Shipping News RSS (ropa, żegluga)",
    "gcaptain.com": "gCaptain RSS (żegluga, ropa)",
    "www.offshore-energy.biz": "Offshore Energy RSS (ropa)",
    "bitcoinmagazine.com": "Bitcoin Magazine RSS (tylko tytuł i link)",
    "silverseek.com": "SilverSeek RSS (srebro; tylko tytuł i link)",
    "goldseek.com": "GoldSeek RSS (złoto; tylko tytuł i link)",
}


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_local(url: str) -> bool:
    return host_of(url) in LOOPBACK


def is_allowed(url: str) -> bool:
    h = host_of(url)
    return h in LOOPBACK or h in DATA_SOURCES
