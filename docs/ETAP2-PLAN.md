# Etap 2 — cechy dzienne, etykiety, analogie (plan, 2026-10-06)

Bez ML, bez UI, bez GDELT (2b).

## Moment decyzji
- Chwila decyzji dnia D: **D 22:00 UTC**. Kalendarze: XAU/XAG/WTI/BRENT — dni robocze USA (pn–pt bez świąt federalnych),
  BTC/ETH — każdy dzień.
- Dwa tory dostępu do danych, oba wyłącznie z known_at <= D 22:00:
  1. **poziomy i zmiany „D vs D−k dni decyzji”** — `db.panel_asof` (ASOF JOIN po known_at na latest_stream),
     wektorowo dla wszystkich dni naraz; zmiana 20d = panel(D) − panel(D−20 dni decyzji) („co wiedzieliśmy wtedy vs teraz”);
  2. **cechy okienkowe** (zwroty, realized vol, średnie 7d, sezonowość zapasów, M2 r/r, funding, OI) — szereg **pierwszych
     publikacji** (wersja o najmniejszym known_at), statystyka okna dostępna od cummax(known_at) okna, dopasowana do D
     przez merge_asof. Konserwatywne: rewizje znane przed D są pomijane (używamy pierwszego wydania).
- Test perturbacji (kopia bazy, wszystkie wartości z known_at > D zmienione) pilnuje obu torów.

## Ceny (src/ms/prices.py)
- XAU/XAG: stitch_metals(Stooq, YF GC=F/SI=F). WTI/BRENT: EIA RWTC/RBRTE + YF CL=F/BZ=F na dni bez EIA — ta sama
  funkcja szwu (uogólniona stitch). BTC/ETH: Binance close.
- Każdy close ma known_at (pierwsza publikacja; dla dni z YF — known_at YF). Wartości <= 0 -> logret NaN + flaga.
- Jednostki sprawdzone u źródła: WALCL, WTREGEN w mln USD, RRPONTSYD w mld -> ×1000.

## features_daily (przebudowywana w całości)
Kolumny: date, asset, feature, grp, value_raw, value_z, short_history. Grupy jak GRAM:
koszt_alternatywny, ryzyko, momentum_pozycje, ropa_podaz, plynnosc (+ krzywa: short_history, poza analogiami).
z-score: kroczący 3 lata na kalendarzu aktywa, okno kończy się w D (włącznie), min 1 rok (252 dni robocze / 365 dni).
Koszyk dolara GRAM: średnia log-zmian 20d USD wobec EUR, JPY, CNY, AUD (DEXUSEU i DEXUSAL odwrócone).
COT: managed money net / OI (disaggregated) dla GOLD/SILVER/WTI/BRENT; BTC/ETH tylko legacy -> noncommercial net / OI.

## labels (osobna tabela)
Na dniach obserwacji ceny aktywa: sigma_5d = std(logret 252 obs do D) × √5; up_5d/down_5d (±1,5σ, suma logret D+1..D+5);
ścieżka 60 obs: ret5/20/60, max DD, dzień dołka, odbicie dołek->D+60, dni do powrotu do ceny z D (NaN, gdy brak).
Start etykiety = zamknięcie D (zawsze >= chwila decyzji albo przed nią z ceną już historyczną — brak przecieku).

## Analogie
z-score cech bez short_history; odległość = średnia po grupach z RMS różnic w grupie (grupa waży tyle samo bez względu
na liczbę cech); kandydat wymaga >= 3 wspólnych grup. k=20, odstęp >= 20 dni, kandydat tylko gdy cała jego 60-dniowa
ścieżka kończy się przed zapytaniem (silniejsze niż „60 dni przed”). Punkt odniesienia: 20 losowych dat z tego samego
tercyla rv60 + rozkład zerowy z 1000 losowań -> percentyl statystyk analogii; 2,5–97,5 percentyl każdej z 4 statystyk
= „nie różnią się od losowych” (10–90 dawałoby ~59% fałszywych różnic przy 4 statystykach).
Kandydat musi mieć pełne etykiety (σ wymaga 252 obs). Raport ostrzega, gdy >50% analogii ma mniej grup niż zapytanie.

## Poprawki po drodze
- FRED (etap 1): obserwacje sprzed archiwum ALFRED dostawały known_at = start archiwum, gdy tabela wydań zaczynała się
  później (VIX 1990–2010 niewidoczny do 2010-11-22). Naprawione; konserwatywny błąd, bez przecieku.
- Jednostki: WALCL/WTREGEN mln USD, RRPONTSYD mld -> ×1000 (sprawdzone w FRED API).
