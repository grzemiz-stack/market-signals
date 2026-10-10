# Etap 1 — plan warstwy danych (2026-10-06)

## Weryfikacja źródeł (2026-10-06)
| # | źródło | stan | start historii |
|---|---|---|---|
| 1 | Stooq xauusd/xagusd | ❌ JS proof-of-work (anty-bot) → **skrzynka data/inbox/stooq/** | — |
| 2 | Binance Vision spot klines 1d | ✅ | 2017-08 |
| 3 | Binance funding (fapi REST) | ✅ BTCUSDT 2019-09-10, ETHUSDT 2019-11-27 | |
| 3 | Bybit funding (v5, 200/str., malejąco) | ✅ BTCUSDT 2020-03-25 | |
| 3 | Binance Vision futures/um metrics (5 min) | ✅ | 2020-09-01 |
| 3 | Deribit DVOL 1D (1000/str., continuation) | ✅ BTC/ETH | 2021-03-24 |
| 4 | EIA RWTC, RBRTE | ✅ v2 seriesid | 1986 / 1987 |
| 5 | EIA WPSR: WCESTUS1, W_EPC0_SAX_YCUOK_MBBL, WCRFPUS2, WPULEUS3 | ✅ | |
| 6 | FRED/ALFRED 25 serii | ✅ wszystkie | |
| 7 | CFTC (cot_reports) | ✅ gold 088691, silver 084691, WTI 067651, Brent NYMEX last day 06765T, BTC 133741, ETH 146021 | 1986 / 2006 |
| 8 | alternative.me F&G | ✅ | 2018-02-01 |
| 8 | NBP tabela A | ✅ | 2002-01-02 |
| 10 | GLD archiwum | ❌ CSV zwraca PDF, strona JS → skrzynka | |
| 10 | SLV (iShares) | tylko bieżące holdingi, brak historii → skrzynka | |
| 10 | LBMA vault | strona bez pliku danych → skrzynka | |
| 1b | GDELT 2.0 | ✅ 400 480 plików, 40 GB zip | 2015-02-18 |

## Decyzje
- `observations` ma dodatkowe kolumny `flags` (np. `nonpositive`, `known_at_rule`, `revised`) i tabelę `series`
  (częstotliwość, opis) — potrzebne do raportu luk i testu 5.
- Czas: TIMESTAMP bez strefy, konwencja **UTC**.
- Ingest jest wersjonujący: wiersz wchodzi tylko, gdy wartość różni się od ostatniej znanej (ASOF po known_at).
  Ponowny import = 0 nowych wierszy. Korekta wartości przy tym samym known_at → known_at = teraz, flaga `revised`.
- known_at:
  - FRED bez vintage: pierwsza data publikacji wydania (FRED release/dates) > koniec okresu obserwacji.
  - ALFRED (*): realtime_start każdego vintage.
  - EIA spot: najbliższa środa po dniu obserwacji, 10:30 ET (reguła, flaga). WPSR: piątek okresu + 5 dni, 10:30 ET, święto → +1 dzień.
  - COT: piątek 15:30 ET po wtorku raportu; święto federalne pn–pt w tygodniu publikacji → najbliższy dzień roboczy po piątku (konserwatywnie); shutdowny oznaczone flagą.
  - Krypto 1d: zamknięcie świecy (open + 1 d). Funding: fundingTime. Metrics: create_time. DVOL: znacznik + 1 d.
  - GPR/TPU/Coin Metrics: czas pobrania snapshotu (dla initial CM: data commita repo).
    **Skutek:** historia sprzed pierwszego snapshotu jest widoczna w as_of() dopiero od daty snapshotu.
- Licencje: public_domain (Fed, EIA, CFTC, FRED-Fed), cc_by (GPR/TPU, EPU, NBP, F&G, GDELT), cc_by_nc (Coin Metrics),
  tos_restricted (Yahoo, Stooq, CBOE VIX/GVZ/OVX, Binance, Bybit, Deribit).

## GDELT (1b) — szacunek, NIE uruchomione
Próba 51 plików: 0,31 s/plik sekwencyjnie, 0,61% wierszy przechodzi filtr (~9 zdarzeń/plik).
- 400 480 plików → ~34 h sekwencyjnie, ~5 h przy 8 równoległych pobraniach; transfer 40 GB.
- Wynik: ~3,7 mln zdarzeń; parquet z wybranymi kolumnami ~0,3–0,5 GB.
- Filtr aktorów: Actor1CountryCode LUB Actor2CountryCode z listy (USA na liście → filtr szeroki).
