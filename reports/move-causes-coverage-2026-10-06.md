# Przyczyny dużych ruchów — kandydaci z kalendarza (2026-10-06)

Etap 4N, krok 1–2 (bez LLM). Plan: docs/ETAP4N-PLAN.md. **Etykiety przyczyn to wiedza po fakcie: tylko do wyjaśniania i badań zdarzeń, nigdy cecha prognozy.**

Duży ruch: |log-zwrot| > 2,5 σ (σ z 252 poprzednich sesji). Zdarzenie -> dzień 0 = pierwsze zamknięcie znane po zdarzeniu; trafienie w dniu 0 (pewność 1,0) lub +1 (0,6).

**Każda etykieta z kalendarza to KANDYDAT** (`status='kandydat'`, `validated=false`): w statusie pokazywana jako „tego dnia było: …”, nigdy jako przyczyna. Przyczynę potwierdza tekst — zwalidowany Qwen albo człowiek.

Ten przebieg dopisał 0 wierszy do `move_causes` (0 = nic nowego, idempotencja).

## Pokrycie na aktywo

| aktywo | okres | duże ruchy | z kandydatem z kalendarza | % | w tym dzień 0 | bez kandydata |
|---|---|---|---|---|---|---|
| XAU | 1971-02-04…2026-06-10 | 447 | 50 | 11 | 24 | 397 |
| XAG | 1965-04-15…2026-02-12 | 501 | 50 | 10 | 25 | 451 |
| WTI | 1987-12-14…2026-09-28 | 282 | 69 | 24 | 37 | 213 |
| BRENT | 1988-07-07…2026-09-10 | 282 | 63 | 22 | 36 | 219 |
| BTC | 2018-11-14…2026-09-21 | 95 | 16 | 17 | 7 | 79 |
| ETH | 2018-09-05…2026-08-19 | 84 | 13 | 15 | 7 | 71 |

## Kandydaci wg typu zdarzenia (rank 1)

| aktywo | typ | kod kandydata | dni |
|---|---|---|---|
| BRENT | fomc | `monetary` | 17 |
| BRENT | gpr | `sovmil` | 10 |
| BRENT | hurricane | `oil_supply` | 4 |
| BRENT | opec | `oil_supply` | 22 |
| BRENT | wpsr | `oil_supply` | 10 |
| BTC | fomc | `monetary` | 7 |
| BTC | hack | `crypto_hack` | 2 |
| BTC | manual | `crypto_etf` | 1 |
| BTC | manual | `leverage_liquidations` | 6 |
| ETH | fomc | `monetary` | 6 |
| ETH | hack | `crypto_hack` | 1 |
| ETH | manual | `crypto_etf` | 1 |
| ETH | manual | `leverage_liquidations` | 5 |
| WTI | fomc | `monetary` | 20 |
| WTI | gpr | `sovmil` | 13 |
| WTI | hurricane | `oil_supply` | 2 |
| WTI | opec | `oil_supply` | 23 |
| WTI | wpsr | `oil_supply` | 11 |
| XAG | fomc | `monetary` | 26 |
| XAG | gpr | `sovmil` | 24 |
| XAU | fomc | `monetary` | 22 |
| XAU | gpr | `sovmil` | 28 |

## Chronologie ropy (P4, P5): duże ruchy WTI/BRENT z wpisem tego samego dnia lub dzień wcześniej

Wpisy nie mają kodu przyczyny — kod nada człowiek (złoto E2) albo zwalidowany Qwen. Tu tylko liczba dopasowań.

| aktywo | źródło | lata wpisów | duże ruchy w tych latach | z wpisem |
|---|---|---|---|---|
| WTI | eia_chron | 1970–2003 | 121 | 21 |
| WTI | wiki_chron | 1934–1997 | 80 | 7 |
| BRENT | eia_chron | 1970–2003 | 117 | 22 |
| BRENT | wiki_chron | 1934–1997 | 75 | 11 |

## Źródła w `cause_events`

| źródło | wpisy | od | do | licencja |
|---|---|---|---|---|
| defillama | 1290 | 2011-06-19 | 2026-10-01 | defillama_terms (niepotwierdzona) |
| eia_chron | 573 | 1970-01-01 | 2003-12-22 | public_domain |
| jk | 606 | 1990-02-08 | 2024-01-31 | academic (niepotwierdzona) |
| manual | 20 | 2012-11-28 | 2025-04-02 | public_facts |
| sffed | 354 | 1988-02-04 | 2023-12-13 | public_domain |
| wiki_chron | 293 | 1934-07-14 | 1997-12-11 | cc_by_sa |
| bbds_codings | 3501 kodowań, 1179 dni | 1900-01-03 | 2022-11-30 | academic (niepotwierdzona) |

## Daty ręczne (P8) niesprawdzone w pełni u źródła: 13

Wchodzą do etykiet z dopiskiem w `evidence`; do sprawdzenia przy następnej okazji.

- china-ico-2017 2017-09-04: nie
- china-exch-2017 2017-09-15: nie
- depeg-dai 2020-03-12: częściowo: Wikipedia podaje marzec 2020 bez dnia
- china-mining-2021 2021-05-21: nie
- depeg-iron 2021-06-16: częściowo: Wikipedia podaje upadek 17.06.2021; spadek TITAN 16.06 (czas USA) — dzień ±1
- depeg-ust 2022-05-09: częściowo: Wikipedia potwierdza krach UST w maju 2022; dzień 9.05 z dokumentu źródeł
- depeg-usdt 2022-05-12: nie
- ftx-binance 2022-11-08: nie
- etf-btc-approval 2024-01-10: nie
- etf-btc-trading 2024-01-11: nie
- etf-eth-approval 2024-05-23: nie
- etf-eth-trading 2024-07-23: nie
- depeg-fdusd 2025-04-02: nie

## Jak to wygląda w statusie (`ms.causes.describe_day`)

- XAU 2013-04-15: tego dnia było: skok AI-GPR (akty) w gazetach z 2013-04-16 (236) — kandydat, przyczyna niepotwierdzona tekstem
- BTC 2020-03-12: tego dnia było: DAI traci parytet, kaskada likwidacji MakerDAO (Black Thursday) [data: częściowo: Wikipedia podaje marzec 2020 bez dnia] — kandydat, przyczyna niepotwierdzona tekstem
- WTI 1991-01-17: przyczyna nieznana (brak zdarzeń w kalendarzu)

## Dni kontrolne (ocena ręczna 2026-10-06 — to nie jest potwierdzenie tekstem)

- BTC/ETH 12.03.2020 (−50% / −59%): `leverage_liquidations` (Black Thursday) — kandydat wiarygodny.
- BTC/ETH 8–9.11.2022: FTX; 9.05.2022: krach UST — kandydaci wiarygodni.
- WTI 6 i 9.03.2020: OPEC+ bez porozumienia (Känzig −8,0) — kandydat wiarygodny.
- **XAU 15.04.2013 (−9,2%, z = −10,5): `sovmil` z AI-GPR (zamach w Bostonie tego dnia) — zbieg dat, NIE przyczyna** (krach złota miał inne powody). Przykład, dlaczego etykieta kalendarza to „zdarzenie tego dnia”, nie przyczyna.
- **BTC/ETH 19.05.2021: `crypto_hack` (Venus Protocol, 100 mln USD) — raczej skutek krachu, nie przyczyna** (w tych dniach chińskie ostrzeżenia z 18.05 — tej daty nie ma w P8).
- **WTI 17.01.1991 (−40% log, Pustynna Burza): brak etykiety kalendarza** — AI-GPR był wysoki od sierpnia 1990, więc nie ma „skoku” względem mediany 90 dni. Wpis jest w chronologii EIA (17.01) — to zadanie dla warstwy badań/Qwena.
- WTI 20.04.2020 (cena ujemna): nie jest „dużym ruchem”, bo log-zwrot przy cenie ≤ 0 jest pusty (zasada z etapu 2).

## Ograniczenia

- FOMC: miara niespodzianki tylko do 2023-12 (SF Fed) / 2024-01 (JK); później etykieta bez wielkości.
- Kalendarz zna jedną możliwą przyczynę: w dniu FOMC ruch mógł mieć inny powód. To etykieta „zdarzenie w tym dniu”, nie dowód przyczyny — dlatego pewność 1,0 / 0,6 to pewność dopasowania daty, nie przyczynowości.
- AI-GPR: wartości przeliczane wstecz (najnowsze wydanie); dzień zdarzenia przyjęty jako d−1 względem gazet.
- Metale: kalendarz ma dla nich tylko FOMC i AI-GPR — reszta czeka na Qwena / komentarze WGC (Priorytet 2).
- P6 (typ decyzji OPEC) czeka na PDF w data/inbox/imf/.
