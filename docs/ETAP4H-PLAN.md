# Etap 4H — testowanie hipotez z docs/MAPA-ZALEZNOSCI.md (plan, 2026-10-06, bez kodu)

Cel: każda hipoteza z mapy (G1–G12, S1–S13, O1–O18, C1–C16) dostaje status z naszych danych. Tekst z literatury
w mapie zostaje nietknięty; status trafia do osobnej, generowanej tabeli. Tylko `potwierdzona` może zostać
kandydatem na cechę w rejestrze modeli (i nadal musi pobić mistrza).

## 1. Inwentarz danych

Oznaczenia testu: **B** beta krocząca współbieżna (Δ czynnika i zwrot w tym samym tygodniu), **P** predykcyjna
(czynnik w tygodniu t → zwrot t+1…t+h), **Z** badanie zdarzeń, **N** hipoteza „brak efektu”, **R** tylko ręcznie /
statystycznie nie do sprawdzenia (dane roczne albo 1–3 zdarzenia).
„Darmowe” sprawdzone 2026-10-06 u źródła (FRED, EIA API v2, Coin Metrics Community), chyba że zaznaczono inaczej.

### Złoto (XAU = Stooq + Yahoo, ms.prices)

| ID | Mamy w market/gdelt | Brakuje | Darmowe? | Ręcznie | Test |
|---|---|---|---|---|---|
| G1 | FRED.DFII10 | — | — | — | B |
| G2 | FRED.T10YIE (od 2003) | — | — | — | B |
| G3 | FRED.DTWEXBGS, koszyk GRAM (FRED.DEX*) | — | — | — | B |
| G4 | FRED.DGS2 (zmiana w dniu FOMC jako miara niespodzianki) | daty posiedzeń FOMC | tak (federalreserve.gov, kalendarz historyczny) | — | Z (znak „sporny” → test dwustronny, bez kierunku z literatury) |
| G5 | FRED.VIXCLS | indeks akcji: NASDAQCOM (od 1971), SP500 (FRED tylko 10 lat — licencja) | tak (FRED) | — | Z (krach = dzienny spadek indeksu w 1% najgorszych) + B na Δ VIX |
| G6 | GPR.GPRD (+ wersja known_at_approx); gdelt.events (konflikty, aktorzy) | — | — | — | B (Δ GPR 7d) + Z (skoki GPR > 95. percentyla) |
| G7 | — | zakupy banków centralnych | IMF IFS (rezerwy złota, mies.) — darmowe, do weryfikacji formatu; WGC — skrzynka (decyzja etapu 1) | WGC xlsx | B kwartalna (mało punktów) albo R |
| G8 | gdelt.events EventCode 163 (sankcje/embargo) | — | — | zamrożenie rezerw 2022 = 1 zdarzenie | Z na sankcjach (GDELT) + R dla 2022 |
| G9 | — | przepływy/holdingi GLD | strona SPDR blokuje automat (etap 1) | skrzynka data/inbox/gld | B po dostarczeniu pliku, inaczej brak danych |
| G10 | COT.disaggregated.GOLD.m_money_* | — | — | — | P (poziom i skrajność net/OI → zwrot 1–8 tyg.) |
| G11 | ceny XAU | — | — | — | P (zwrot 1/3/6/12 mies. → zwrot kolejnego miesiąca) |
| G12 | — | cło Indii (daty), import Indii | dane rządowe, PDF | tak | R |

### Srebro (XAG)

| ID | Mamy | Brakuje | Darmowe? | Ręcznie | Test |
|---|---|---|---|---|---|
| S1 | XAU, XAG | — | — | — | B (beta srebra do złota) |
| S2 | FRED.DFII10 | miedź PCOPPUSDM (mies., od 1992), INDPRO (mies.), ISM PMI | miedź i INDPRO tak (FRED); ISM nie (płatne) | — | B miesięczna (zmiany r/r i m/m) bez PMI |
| S3 | FRED.DFII10, DTWEXBGS, M2SL | — | — | — | N (oczekiwany brak efektu) |
| S4 | — | popyt PV (rocznie) | raporty WSS (PDF) | tak | R |
| S5 | — | podaż kopalń (rocznie) | WSS (PDF) | tak | R |
| S6 | — | deficyt rynku (rocznie, rewidowany) | WSS (PDF) | tak | R |
| S7 | — | lease rate, free float LBMA | LBMA: warunki ograniczają | skrzynka data/inbox/lbma | brak danych do czasu pliku |
| S8 | — | daty decyzji celnych / critical minerals | — | tak (2–3 zdarzenia) | R |
| S9 | — | holdingi SLV (historia) | iShares daje tylko bieżące | skrzynka data/inbox/slv | brak danych |
| S10 | ceny XAG | import Indii (mies.) | dane rządowe | tak | B sezonowa (X–XI vs reszta roku) na cenach + R dla importu |
| S11 | — | daty podwyżek marginesów CME | strony CME blokują automat | tak (lista dat) | Z po dostarczeniu listy |
| S12 | XAU/XAG (ratio liczone) | — | — | — | P (wysoki ratio → względny zwrot XAG−XAU w 3–12 mies.) |
| S13 | COT.disaggregated.SILVER.m_money_* | — | — | — | P |

### Ropa (WTI, BRENT; test osobno dla obu)

| ID | Mamy | Brakuje | Darmowe? | Ręcznie | Test |
|---|---|---|---|---|---|
| O1 | EIA.WCRFPUS2 (produkcja USA) | szoki podażowe Baumeister–Hamilton / Kilian (mies.), produkcja światowa | tak (pliki autorów; EIA API) | — | B miesięczna |
| O2 | — | IGREA (mies., od 1968) | tak (FRED IGREA) | — | B miesięczna z opóźnieniem 0–6 mies. |
| O3 | FRED.OVXCLS, gdelt.events (konflikty u producentów) | identyfikacja szoku „strachu” | — | — | Z (skoki konfliktów GDELT u producentów) |
| O4 | GPR.GPRD_ACT/THREAT; gdelt.events z podziałem aktorów (producenci ropy vs reszta) | GPR energetyczny ECB | ECB — nieopublikowany jako szereg | — | B osobno dla „energetycznego” (GDELT, producenci) i „nieenergetycznego” |
| O5 | ceny WTI/BRENT | daty komunikatów OPEC+ (Känzig: 1983–2017+) | tak (dane Känziga) | dopisywanie nowych dat | Z |
| O6 | EIA.WCESTUS1 + czas publikacji (known_at) | konsensus analityków | nie (płatne) | — | Z na proxy: zmiana − średnia sezonowa (jak w decomp); oznaczone „proxy” |
| O7 | CURVE.* (od 2026-10) | historia M1–M4 | EIA RCLC1–RCLC4 do 2024-04-05 (darmowe); luka 2024-04…2026-10 | — | B/P na 1986–2024 (spread M4/M1) |
| O8 | EIA.WCESTUS1, CUSHING (USA) | zapasy OECD (STEO, mies.) | tak (EIA API) | — | B miesięczna |
| O9 | COT.disaggregated.WTI/BRENT.m_money_* | — | — | — | P |
| O10 | EIA.RWTC | benzyna NY (EER_EPMRU_PF4_Y35NY_DPG), olej opałowy/ULSD (EER_EPD2F_PF4_Y35NY_DPG) | tak (EIA API, sprawdzone) | — | B (crack 3-2-1 liczony) |
| O11 | — | import i zapasy Chin | brak oficjalnych zapasów | tak | R |
| O12 | FRED.DTWEXBGS, koszyk GRAM | — | — | — | B (znak niestabilny — test podokresów przed/po 2019) |
| O13 | — | huragany (NOAA HURDAT2) | tak (public domain) | — | Z (wejście huraganu do Zatoki) |
| O14 | gdelt.events z ActionGeo_Lat/Long (Ormuz, Morze Czerwone) | — | — | — | Z |
| O15 | gdelt.events EventCode 163 (aktorzy RUS, IRN) | dyskonto Urals | nie (płatne) | — | Z na sankcjach; dyskonto R |
| O16 | — | zapasy SPR (WCSSTUS1, tyg., od 1982) | tak (EIA API, sprawdzone) | — | B |
| O17 | — | rigi Baker Hughes | skrzynka (Akamai) | archiwum BH (zapisane w STAN) | B po dostarczeniu, inaczej brak danych |
| O18 | FRED.OVXCLS, baseline_eval | — | — | — | już zbadane w 3A (rejestr) — tylko przepisanie wyniku |

### Krypto (BTC, ETH; test osobno dla obu)

| ID | Mamy | Brakuje | Darmowe? | Ręcznie | Test |
|---|---|---|---|---|---|
| C1 | ceny Binance | — | — | — | P (zwrot tygodnia t → t+1…t+4), osobno 2017–2019 i 2020–2026 |
| C2 | — | Google Trends | nieoficjalne API (bez gwarancji, limity) | CSV z przeglądarki | P po dostarczeniu, inaczej brak danych |
| C3 | — | lista hacków giełd | listy publiczne | tak | Z po dostarczeniu listy |
| C4 | — | NASDAQCOM (FRED, od 1971), SP500 (10 lat) | tak | — | B (dzienna i tygodniowa), podokresy przed/po 2020 |
| C5 | FRED.DGS2, EFFR, FEDFUNDS | daty FOMC (jak G4) | tak | — | Z + B na Δ DGS2, przed/po 2020 |
| C6 | FRED.M2SL, WALCL (płynność netto jak w cechach) | globalne M2 | częściowo (M2 innych krajów w FRED, mies.) | — | B na zmianach (nie poziomach) |
| C7 | FRED.DTWEXBGS, koszyk GRAM | — | — | — | B |
| C8 | — | przepływy do spot ETF BTC/ETH | strony agregatorów | CSV ręcznie | B po dostarczeniu |
| C9 | — | podaż stablecoinów (Coin Metrics usdt/usdc SplyCur) | tak (Community API, sprawdzone) | — | P (Δ podaży → zwrot) i odwrotnie (kierunek przyczynowy) |
| C10 | — | lista zdarzeń regulacyjnych | — | tak | Z po dostarczeniu |
| C11 | BTCUSDT/ETHUSDT.funding.binance i .bybit | — | — | — | P (skrajny funding → zwrot 1–4 tyg.) |
| C12 | sum_open_interest (Binance metrics) | likwidacje (historia) | brak darmowej pełnej historii | — | P (wzrost OI → wielkość ruchu, nie kierunek) |
| C13 | FNG.crypto | — | — | — | B współbieżna + P kontrariańska 30–90 dni |
| C14 | GPR.GPRD, gdelt.events | — | — | — | B (średnio ≈ 0: test N) + Z (start konfliktu) |
| C15 | ceny BTC (od 2017: halvingi 2020, 2024) | — | — | — | R (2 zdarzenia) |
| C16 | ceny ETH/BTC | przepływy ETF ETH, skarbce spółek | — | CSV ręcznie | R / brak danych |

### Podsumowanie inwentarza
- Testowalne od razu na danych w bazie: **G1, G2, G3, G6, G10, G11, S1, S3, S10 (sezon), S12, S13, O9, O12, O18, C1, C7, C11, C12, C13, C14** (+ G8/O3/O4/O14/O15 po zakończeniu backfillu GDELT).
- Wymagają **darmowych** nowych serii (do Twojej zgody — nowe źródła): NASDAQCOM, SP500 (FRED), IGREA, PCOPPUSDM, INDPRO
  (FRED), RCLC1–4, WCSSTUS1, benzyna/ULSD NY (EIA API), stablecoiny usdt/usdc (Coin Metrics), daty FOMC
  (federalreserve.gov), daty OPEC (dane Känziga), HURDAT2 (NOAA), szoki Baumeister–Hamilton (plik autorów).
  Odblokowują: G4, G5, S2, O1, O2, O5, O7, O8, O10, O13, O16, C4, C5, C9.
- **Tylko ręcznie / statystycznie nie do sprawdzenia:** G7 (jeśli bez IMF), G9, G12, S4–S9, S11, O6 (konsensus), O11, O15
  (dyskonto), O17, C2, C3, C8, C10, C15, C16.

## 2. Metoda (wg sekcji „Jak testujemy” mapy)

- **Tygodnie** jak w dekompozycji: piątek 22:00 UTC (krypto: niedziela 24:00), wartości znane na koniec tygodnia
  (panel_asof / pierwsze publikacje). Zmiany, nie poziomy (zasada 5 mapy). Serie miesięczne: test miesięczny.
- **Beta krocząca:** OLS jednoczynnikowa, okna 52 i 156 tygodni, ±2 SE (HC3; dla horyzontów > 1 tyg. Newey–West),
  % okien ze znakiem z literatury i % okien istotnych z tym znakiem, w całej historii i w ostatnich 3 latach.
- **Test główny (do BH):** ostatnie 156 tygodni (ostatnie 3 lata), jedna wartość p na parę (ID, aktywo).
- **Badanie zdarzeń:** skumulowany zwrot w oknach [0,+1], [0,+5], [0,+20] dni sesyjnych vs rozkład tych samych okien
  dla losowych dat (10 000 losowań, bez nakładania na zdarzenia) -> percentyl i p. Daty zdarzeń z known_at
  (GDELT: DATEADDED; FOMC/OPEC: dzień komunikatu).
- **Korekta Benjamini–Hochberg** (q = 0,10) na całej tabeli testów głównych; liczba testów i ich lista w tabeli
  `runs` (stage `4H`, params = lista testów, note = wersja). Każde ponowne uruchomienie z tą samą listą = rerun,
  nowa lista = nowa próba (jak w 3B).
- **Status** (dla pary ID × aktywo):
  - `potwierdzona`: test główny istotny po BH, znak zgodny z literaturą, ≥ 70% okien 52-tyg. w ostatnich 3 latach
    z tym znakiem;
  - `odwrócona`: test główny istotny po BH ze znakiem przeciwnym;
  - `osłabła`: test główny nieistotny, ale wcześniej (okna 156-tyg. przed ostatnimi 3 latami) ≥ 60% okien istotnych
    ze znakiem z literatury;
  - `brak danych`: brak serii albo < 104 tygodnie obserwacji;
  - `nie do sprawdzenia`: dane roczne / ≤ 3 zdarzenia (wiersze R);
  - `niepotwierdzona`: test główny nieistotny i wcześniej też nie (nie spełnia warunku `osłabła`).
  - Hipotezy „brak efektu” (S3, część C14): `potwierdzona`, gdy test nieistotny i |beta| mała (CI w ±0,1 SD efektu).
  - Znak „sporny” (G4, C9): status opisowy ze znakiem znalezionym u nas; nigdy `potwierdzona` jako cecha bez kierunku.
- **Do Twojej decyzji:** hipoteza, która nigdy nie była istotna u nas, nie pasuje do żadnego z 5 statusów mapy.
  Proponuję szósty: `niepotwierdzona`. Bez niego musiałbym ją wpisać jako `osłabła`, co sugeruje, że kiedyś działała.

## 3. Wynik i zapis

- `reports/hipotezy-{data}.md`: tabela ID × aktywo → beta 3 lata [CI], p, p po BH, % okien zgodnych (52/156, całość
  i 3 lata), wynik zdarzeń, **Status**, użyte serie; wykresy-tabele bety kroczącej dla G1, G3, S1, O12, C4.
- Tabela `hypothesis_status` w market.duckdb (id, asset, status, beta, ci, p, p_bh, tested_at, run_id) — z niej
  rejestr bierze kandydatów na cechy: **tylko `potwierdzona`**.
- Mapa: osobna tabela „Status testów (generowane — nie edytować)” dopisana na końcu pliku między znacznikami
  `<!-- STATUS:START -->` i `<!-- STATUS:END -->`. Test w bramce: wszystko poza znacznikami bajt w bajt identyczne
  z wersją z gita (sha256). Warunek: **najpierw commit obecnej mapy bez zmian** (teraz jest nieśledzona).

## 4. Kolejność (po Twojej akceptacji)
1. Commit mapy w obecnej postaci.
2. Moduł testów (ms/hypotheses.py) + testy jednostkowe (BH, status, beta krocząca na danych syntetycznych, ochrona
   tekstu mapy, brak przyszłości w tygodniach).
3. Przebieg na danych w bazie (lista „testowalne od razu”) -> raport, status w mapie, commit.
4. Po zakończeniu GDELT: szeregi zdarzeń (konflikty u producentów, Ormuz/Morze Czerwone, sankcje) -> G6/G8/O3/O4/O14/O15/C14.
5. Po Twojej zgodzie na darmowe źródła: kolektory + testy pozostałych.
6. Wiersze ręczne: status `nie do sprawdzenia` / `brak danych`, dopóki nie trafią pliki do skrzynek.

## Decyzje (2026-10-06)
- Szósty status **`niepotwierdzona`** (na naszych danych nigdy nie była istotna) — dodany też w mapie, w punkcie 3
  „Jak testujemy”: jedyna dozwolona zmiana tekstu mapy. Ochrona: tools/check_mapa.py + tools/mapa_tekst.sha256 w bramce.
- Darmowe źródła: wszystkie z listy **oprócz SP500** (wystarczy NASDAQCOM). Krzywa RCLC1–4 tylko do 2024-04-05;
  luka do snapshotów oznaczona flagą, **bez wypełniania przybliżeniem**.
- Raport: obok testu głównego (3 lata) wynik dla całej historii i opis zmiany reżimu wprost.
- Kolejność: 20 hipotez testowalnych od razu -> raport, commit; potem nowe źródła; GDELT na końcu.
