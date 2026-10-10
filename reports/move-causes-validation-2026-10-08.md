# Walidacja klasyfikatora przyczyn (Qwen, lokalnie) — 2026-10-08

Plan i progi: docs/ETAP4N-WALIDACJA-PLAN.md (progi z 2026-10-06, κ_ludzie z 2026-10-07 przed uruchomieniem). `validated = true` tylko gdy E1, E2 (z wariantem zamaskowanym) i E4 przeszły; E3 to kontrola (decyzja 2026-10-07).
## Porównanie prób (1–2: prompt v1; 3: prompt v2, ostatnia — po niej koniec etapu)

| model                              | prompt   | E1    | E4    | E3 (kontrola)   | E2   | validated   | E4-hist   |
|:-----------------------------------|:---------|:------|:------|:----------------|:-----|:------------|:----------|
| qwen3:30b-a3b-instruct-2507-q4_K_M | v1       | False | False | 4/7             | True | False       | —         |
| qwen2.5-coder:32b                  | v1       | False | False | 3/7             | True | False       | —         |
| qwen3:30b-a3b-instruct-2507-q4_K_M | v2       | False | —     | 4/7             | True | False       | False     |


## qwen3:30b-a3b-instruct-2507-q4_K_M (digest 19e422b02313, prompt v1 98dc8d39f7050718)

**Progi akceptacji i kiedy zapisane:**

- E1: κ(model, człowiek) ≥ 0.695 = max(0,60; κ_ludzie 0,795 − 0,10); reguła z planu 4N (2026-10-06), wartość w DECISIONS i commicie `d488231` (2026-10-07 09:55:36 UTC).
- E4: zgodność z kalendarzem ≥ 0.6 (plan 4N, 2026-10-06).
- Pierwsza odpowiedź modelu w walidacji: 2026-10-07 12:29:16.764113 UTC → progi zapisane **PRZED** przebiegami.

**E1 (BBDS 1950–2022, n = 492, bez odpowiedzi 0)**: dokładność 0.669, κ 0.595 [0.530; 0.657] — próg κ ≥ 0.695 → **NIEZALICZONE**

Macierz pomyłek (wiersze: człowiek, kolumny: model):

| gold              |   commodities |   corporate_foreign |   elections |   fiscal |   fx_capital |   macro |   monetary |   regulation |   sovmil |   terror |   trade_policy |   unknown |
|:------------------|--------------:|--------------------:|------------:|---------:|-------------:|--------:|-----------:|-------------:|---------:|---------:|---------------:|----------:|
| commodities       |            15 |                   0 |           0 |        0 |            0 |       1 |          0 |            0 |        0 |        0 |              0 |         0 |
| corporate_foreign |             0 |                  60 |           0 |        0 |            0 |      13 |          6 |            0 |        1 |        0 |              0 |         1 |
| elections         |             0 |                   0 |           9 |        0 |            0 |       2 |          1 |            0 |        2 |        0 |              0 |         1 |
| fiscal            |             0 |                   1 |           0 |       37 |            3 |       8 |          4 |            2 |        3 |        0 |              0 |         0 |
| fx_capital        |             0 |                   0 |           0 |        0 |            3 |       0 |          0 |            0 |        0 |        0 |              0 |         0 |
| macro             |             0 |                   6 |           0 |        8 |            9 |     109 |         49 |            0 |        1 |        1 |              1 |         2 |
| monetary          |             0 |                   1 |           0 |        1 |            0 |       0 |         52 |            0 |        0 |        0 |              0 |         0 |
| regulation        |             0 |                   2 |           0 |        1 |            0 |       0 |          2 |            1 |        2 |        2 |              0 |         0 |
| sovmil            |             0 |                   0 |           1 |        0 |            0 |       0 |          0 |            0 |       16 |        0 |              0 |         0 |
| terror            |             0 |                   0 |           0 |        0 |            0 |       0 |          0 |            0 |        0 |        5 |              0 |         0 |
| trade_policy      |             0 |                   0 |           0 |        0 |            0 |       0 |          0 |            0 |        0 |        0 |              5 |         0 |
| unknown           |             0 |                   4 |           0 |        1 |            2 |      11 |          4 |            0 |        3 |        0 |              0 |        17 |

**E4 (dni kalendarza 2015–2026, n = 42)**: zgodność 0/42 = 0.000 [Wilson 0.000; 0.084] — próg ≥ 0.6 → **NIEZALICZONE**

| gold        |   global_demand |   macro |   sovmil |   terror |   trade_policy |   unknown |
|:------------|----------------:|--------:|---------:|---------:|---------------:|----------:|
| crypto_etf  |               0 |       0 |        2 |        0 |              0 |         0 |
| crypto_hack |               0 |       0 |        2 |        0 |              0 |         0 |
| monetary    |               1 |       2 |       16 |        4 |              1 |         2 |
| oil_supply  |               1 |       1 |        4 |        2 |              2 |         2 |

### E3 — kontrola (nie bramka; decyzja 2026-10-07: n małe)

Epizody liczone (bez spornych): 4/7 trafień; wariant zamaskowany 3/7; spadek +0.14 (sygnał odpowiadania z pamięci, gdy > 0,15).

| epizod   | literatura    | model         | model (zamaskowany)   |
|:---------|:--------------|:--------------|:----------------------|
| E3-01    | global_demand | supply        | supply                |
| E3-03    | supply        | supply        | supply                |
| E3-05    | supply        | supply        | supply                |
| E3-06    | precautionary | supply        | supply                |
| E3-07    | global_demand | supply        | supply                |
| E3-08    | global_demand | global_demand | supply                |
| E3-09    | supply        | supply        | supply                |

Epizody sporne (poza metryką) — odpowiedź modelu obok obu wersji ze źródeł:

| epizod   | Hamilton (2011)   | Baumeister–Kilian (2016)   | model   | model (zamaskowany)   |
|:---------|:------------------|:---------------------------|:--------|:----------------------|
| E3-02    | supply            | global_demand              | supply  | supply                |
| E3-04    | supply            | precautionary              | supply  | supply                |

### E2 — komentarze WGC (wzorzec: zdanie WGC + kod przypisany wg ref/e2_wgc_rules.md, nie przez Qwena)

Próg (bez zmian): dokładność ≥ 0.75 i κ ≥ 0.6, oba warianty.

- wariant zwykły: n = 30, dokładność 0.900 [Wilson 0.744; 0.965], κ 0.865
- wariant zamaskowany: n = 30, dokładność 0.800 [Wilson 0.627; 0.905], κ 0.726
- **n ≈ 30: wynik bliski progu nie jest rozstrzygający** (przedział dokładności ma szerokość rzędu ±0,15).
- niezależna kontrola wzorca (subagent, 20 wierszy): NIE = 0 z 20 (bramka: ≤ 3); runda 1: NIE = 7 → kierunek A
- spadek dokładności po zamaskowaniu: +0.100 (sygnał pamięci, gdy > 0,15)
- → **ZALICZONE**

Wiersze wzorca zależne od konwencji: **19 z 30** (dolar -> fx_capital: 11, rentowności / stopy -> monetary: 6, stopy po wskazanej publikacji danych -> macro: 1, zakupy złota przez banki centralne -> monetary: 1). Konwencje są w definicjach kodów (ref/taxonomy.csv, kolumna prompt) — model je widzi.

- zależne od konwencji: trafienia 17/19 (0.895)
- niezależne: trafienia 10/11 (0.909)

Ograniczenie wzorca (odnotowane, wzorzec bez zmian): 2023-10 (komentarz WGC o ataku z 7 października; cytat poza kopią publiczną) → sovmil — niezależna kontrola (runda 3) dała TAK, ale zauważyła, że strona niepaństwowa słabo pasuje do definicji „geopolitical tensions between states” (bliżej `terror`).

| gold         |   fx_capital |   macro |   monetary |   sovmil |   trade_policy |
|:-------------|-------------:|--------:|-----------:|---------:|---------------:|
| fx_capital   |           10 |       1 |          0 |        0 |              0 |
| macro        |            0 |       5 |          0 |        0 |              0 |
| monetary     |            1 |       0 |          7 |        0 |              0 |
| sovmil       |            0 |       0 |          1 |        3 |              0 |
| trade_policy |            0 |       0 |          0 |        0 |              2 |


**Werdykt: validated = false** (bramka: E1, E2 z wariantem zamaskowanym, E4; E3 to kontrola; wyniki: {'E1': False, 'E4': False, 'E3 (kontrola)': '4/7', 'E2': True}).

## qwen2.5-coder:32b (digest b92d6a0bd47e, prompt v1 98dc8d39f7050718)

**Progi akceptacji i kiedy zapisane:**

- E1: κ(model, człowiek) ≥ 0.695 = max(0,60; κ_ludzie 0,795 − 0,10); reguła z planu 4N (2026-10-06), wartość w DECISIONS i commicie `d488231` (2026-10-07 09:55:36 UTC).
- E4: zgodność z kalendarzem ≥ 0.6 (plan 4N, 2026-10-06).
- Pierwsza odpowiedź modelu w walidacji: 2026-10-07 13:16:00.981525 UTC → progi zapisane **PRZED** przebiegami.

**E1 (BBDS 1950–2022, n = 492, bez odpowiedzi 0)**: dokładność 0.665, κ 0.598 [0.536; 0.655] — próg κ ≥ 0.695 → **NIEZALICZONE**

Macierz pomyłek (wiersze: człowiek, kolumny: model):

| gold              |   commodities |   corporate_foreign |   elections |   fiscal |   fx_capital |   macro |   monetary |   sovmil |   terror |   trade_policy |   unknown |
|:------------------|--------------:|--------------------:|------------:|---------:|-------------:|--------:|-----------:|---------:|---------:|---------------:|----------:|
| commodities       |            12 |                   0 |           0 |        0 |            0 |       4 |          0 |        0 |        0 |              0 |         0 |
| corporate_foreign |             1 |                  59 |           0 |        1 |            1 |      12 |          5 |        1 |        0 |              0 |         1 |
| elections         |             0 |                   0 |           8 |        1 |            0 |       0 |          1 |        3 |        0 |              0 |         2 |
| fiscal            |             0 |                   3 |           0 |       41 |            2 |       1 |          5 |        4 |        0 |              0 |         2 |
| fx_capital        |             0 |                   0 |           0 |        0 |            3 |       0 |          0 |        0 |        0 |              0 |         0 |
| macro             |             0 |                   4 |           0 |        8 |            7 |      98 |         51 |       10 |        0 |              3 |         5 |
| monetary          |             0 |                   0 |           0 |        0 |            1 |       1 |         52 |        0 |        0 |              0 |         0 |
| regulation        |             0 |                   1 |           0 |        1 |            0 |       0 |          4 |        3 |        0 |              0 |         1 |
| sovmil            |             0 |                   0 |           1 |        0 |            0 |       0 |          0 |       16 |        0 |              0 |         0 |
| terror            |             0 |                   0 |           0 |        0 |            0 |       0 |          0 |        0 |        5 |              0 |         0 |
| trade_policy      |             0 |                   0 |           0 |        0 |            0 |       0 |          0 |        0 |        0 |              5 |         0 |
| unknown           |             1 |                   0 |           2 |        1 |            0 |       3 |          4 |        3 |        0 |              0 |        28 |

**E4 (dni kalendarza 2015–2026, n = 42)**: zgodność 0/42 = 0.000 [Wilson 0.000; 0.084] — próg ≥ 0.6 → **NIEZALICZONE**

| gold        |   global_demand |   sovmil |   terror |   trade_policy |   unknown |
|:------------|----------------:|---------:|---------:|---------------:|----------:|
| crypto_etf  |               0 |        2 |        0 |              0 |         0 |
| crypto_hack |               0 |        2 |        0 |              0 |         0 |
| monetary    |               2 |       12 |        1 |              1 |        10 |
| oil_supply  |               1 |        5 |        1 |              2 |         3 |

### E3 — kontrola (nie bramka; decyzja 2026-10-07: n małe)

Epizody liczone (bez spornych): 3/7 trafień; wariant zamaskowany 3/7; spadek +0.00 (sygnał odpowiadania z pamięci, gdy > 0,15).

| epizod   | literatura    | model         | model (zamaskowany)   |
|:---------|:--------------|:--------------|:----------------------|
| E3-01    | global_demand | supply        | supply                |
| E3-03    | supply        | supply        | supply                |
| E3-05    | supply        | supply        | supply                |
| E3-06    | precautionary | precautionary | supply                |
| E3-07    | global_demand | supply        | supply                |
| E3-08    | global_demand | precautionary | global_demand         |
| E3-09    | supply        | precautionary | precautionary         |

Epizody sporne (poza metryką) — odpowiedź modelu obok obu wersji ze źródeł:

| epizod   | Hamilton (2011)   | Baumeister–Kilian (2016)   | model   | model (zamaskowany)   |
|:---------|:------------------|:---------------------------|:--------|:----------------------|
| E3-02    | supply            | global_demand              | supply  | supply                |
| E3-04    | supply            | precautionary              | supply  | supply                |

### E2 — komentarze WGC (wzorzec: zdanie WGC + kod przypisany wg ref/e2_wgc_rules.md, nie przez Qwena)

Próg (bez zmian): dokładność ≥ 0.75 i κ ≥ 0.6, oba warianty.

- wariant zwykły: n = 30, dokładność 0.933 [Wilson 0.787; 0.982], κ 0.911
- wariant zamaskowany: n = 30, dokładność 0.867 [Wilson 0.703; 0.947], κ 0.822
- **n ≈ 30: wynik bliski progu nie jest rozstrzygający** (przedział dokładności ma szerokość rzędu ±0,15).
- niezależna kontrola wzorca (subagent, 20 wierszy): NIE = 0 z 20 (bramka: ≤ 3); runda 1: NIE = 7 → kierunek A
- spadek dokładności po zamaskowaniu: +0.067 (sygnał pamięci, gdy > 0,15)
- → **ZALICZONE**

Wiersze wzorca zależne od konwencji: **19 z 30** (dolar -> fx_capital: 11, rentowności / stopy -> monetary: 6, stopy po wskazanej publikacji danych -> macro: 1, zakupy złota przez banki centralne -> monetary: 1). Konwencje są w definicjach kodów (ref/taxonomy.csv, kolumna prompt) — model je widzi.

- zależne od konwencji: trafienia 18/19 (0.947)
- niezależne: trafienia 10/11 (0.909)

Ograniczenie wzorca (odnotowane, wzorzec bez zmian): 2023-10 (komentarz WGC o ataku z 7 października; cytat poza kopią publiczną) → sovmil — niezależna kontrola (runda 3) dała TAK, ale zauważyła, że strona niepaństwowa słabo pasuje do definicji „geopolitical tensions between states” (bliżej `terror`).

| gold         |   fx_capital |   macro |   monetary |   sovmil |   trade_policy |
|:-------------|-------------:|--------:|-----------:|---------:|---------------:|
| fx_capital   |           11 |       0 |          0 |        0 |              0 |
| macro        |            0 |       4 |          1 |        0 |              0 |
| monetary     |            0 |       0 |          7 |        0 |              1 |
| sovmil       |            0 |       0 |          0 |        4 |              0 |
| trade_policy |            0 |       0 |          0 |        0 |              2 |


**Werdykt: validated = false** (bramka: E1, E2 z wariantem zamaskowanym, E4; E3 to kontrola; wyniki: {'E1': False, 'E4': False, 'E3 (kontrola)': '3/7', 'E2': True}).

## qwen3:30b-a3b-instruct-2507-q4_K_M (digest 19e422b02313, prompt v2 4f3242dd21f09b54)

**Progi akceptacji i kiedy zapisane:**

- E1: κ(model, człowiek) ≥ 0.695 = max(0,60; κ_ludzie 0,795 − 0,10); reguła z planu 4N (2026-10-06), wartość w DECISIONS i commicie `d488231` (2026-10-07 09:55:36 UTC).
- E4: zgodność z kalendarzem ≥ 0.6 (plan 4N, 2026-10-06).
- Pierwsza odpowiedź modelu w walidacji: 2026-10-08 08:55:05.487053 UTC → progi zapisane **PRZED** przebiegami.

**E1 (BBDS 1950–2022, n = 492, bez odpowiedzi 0)**: dokładność 0.701, κ 0.628 [0.561; 0.686] — próg κ ≥ 0.695 → **NIEZALICZONE**

Macierz pomyłek (wiersze: człowiek, kolumny: model):

| gold              |   commodities |   corporate_foreign |   elections |   fiscal |   fx_capital |   macro |   monetary |   regulation |   sovmil |   terror |   trade_policy |   unknown |
|:------------------|--------------:|--------------------:|------------:|---------:|-------------:|--------:|-----------:|-------------:|---------:|---------:|---------------:|----------:|
| commodities       |            14 |                   0 |           0 |        0 |            0 |       2 |          0 |            0 |        0 |        0 |              0 |         0 |
| corporate_foreign |             0 |                  57 |           0 |        0 |            0 |      17 |          6 |            0 |        0 |        0 |              0 |         1 |
| elections         |             0 |                   0 |           9 |        0 |            0 |       2 |          1 |            0 |        2 |        0 |              0 |         1 |
| fiscal            |             0 |                   1 |           0 |       38 |            3 |       9 |          4 |            0 |        3 |        0 |              0 |         0 |
| fx_capital        |             0 |                   0 |           0 |        0 |            3 |       0 |          0 |            0 |        0 |        0 |              0 |         0 |
| macro             |             0 |                   6 |           0 |        8 |            9 |     128 |         30 |            0 |        1 |        1 |              1 |         2 |
| monetary          |             0 |                   0 |           0 |        1 |            0 |       1 |         52 |            0 |        0 |        0 |              0 |         0 |
| regulation        |             0 |                   2 |           0 |        1 |            0 |       0 |          2 |            1 |        2 |        2 |              0 |         0 |
| sovmil            |             0 |                   0 |           1 |        0 |            0 |       0 |          0 |            0 |       16 |        0 |              0 |         0 |
| terror            |             0 |                   0 |           0 |        0 |            0 |       0 |          0 |            0 |        0 |        5 |              0 |         0 |
| trade_policy      |             0 |                   0 |           0 |        0 |            0 |       0 |          0 |            0 |        0 |        0 |              5 |         0 |
| unknown           |             0 |                   3 |           0 |        1 |            0 |      14 |          4 |            0 |        3 |        0 |              0 |        17 |

**E4-hist (pełne GDELT 2.0 export + mentions, 42 dni, n = 42)**: zgodność 0/42 = 0.000 [Wilson 0.000; 0.084] — próg ≥ 0.6 → **NIEZALICZONE**
Diagnostyka (bez wpływu na wynik): odsetek pozycji USA–USA wśród wybranych — mediana 0.18.

| gold        |   corporate_foreign |   crypto_hack |   elections |   fiscal |   global_demand |   macro |   monetary |   sovmil |   terror |   trade_policy |   unknown |
|:------------|--------------------:|--------------:|------------:|---------:|----------------:|--------:|-----------:|---------:|---------:|---------------:|----------:|
| crypto_etf  |                   0 |             0 |           0 |        0 |               0 |       0 |          0 |        2 |        0 |              0 |         0 |
| crypto_hack |                   0 |             0 |           0 |        0 |               0 |       0 |          1 |        1 |        0 |              0 |         0 |
| monetary    |                   0 |             0 |           1 |        2 |               0 |       6 |          0 |       10 |        3 |              2 |         2 |
| oil_supply  |                   1 |             2 |           1 |        0 |               1 |       1 |          0 |        3 |        0 |              2 |         1 |

### E3 — kontrola (nie bramka; decyzja 2026-10-07: n małe)

Epizody liczone (bez spornych): 4/7 trafień; wariant zamaskowany 3/7; spadek +0.14 (sygnał odpowiadania z pamięci, gdy > 0,15).

| epizod   | literatura    | model         | model (zamaskowany)   |
|:---------|:--------------|:--------------|:----------------------|
| E3-01    | global_demand | supply        | supply                |
| E3-03    | supply        | supply        | supply                |
| E3-05    | supply        | supply        | supply                |
| E3-06    | precautionary | supply        | supply                |
| E3-07    | global_demand | supply        | supply                |
| E3-08    | global_demand | global_demand | supply                |
| E3-09    | supply        | supply        | supply                |

Epizody sporne (poza metryką) — odpowiedź modelu obok obu wersji ze źródeł:

| epizod   | Hamilton (2011)   | Baumeister–Kilian (2016)   | model   | model (zamaskowany)   |
|:---------|:------------------|:---------------------------|:--------|:----------------------|
| E3-02    | supply            | global_demand              | supply  | supply                |
| E3-04    | supply            | precautionary              | supply  | supply                |

### E2 — komentarze WGC (wzorzec: zdanie WGC + kod przypisany wg ref/e2_wgc_rules.md, nie przez Qwena)

Próg (bez zmian): dokładność ≥ 0.75 i κ ≥ 0.6, oba warianty.

- wariant zwykły: n = 30, dokładność 0.800 [Wilson 0.627; 0.905], κ 0.729
- wariant zamaskowany: n = 30, dokładność 0.767 [Wilson 0.591; 0.882], κ 0.681
- **n ≈ 30: wynik bliski progu nie jest rozstrzygający** (przedział dokładności ma szerokość rzędu ±0,15).
- niezależna kontrola wzorca (subagent, 20 wierszy): NIE = 0 z 20 (bramka: ≤ 3); runda 1: NIE = 7 → kierunek A
- spadek dokładności po zamaskowaniu: +0.033 (sygnał pamięci, gdy > 0,15)
- → **ZALICZONE**

Wiersze wzorca zależne od konwencji: **19 z 30** (dolar -> fx_capital: 11, rentowności / stopy -> monetary: 6, stopy po wskazanej publikacji danych -> macro: 1, zakupy złota przez banki centralne -> monetary: 1). Konwencje są w definicjach kodów (ref/taxonomy.csv, kolumna prompt) — model je widzi.

- zależne od konwencji: trafienia 14/19 (0.737)
- niezależne: trafienia 10/11 (0.909)

Ograniczenie wzorca (odnotowane, wzorzec bez zmian): 2023-10 (komentarz WGC o ataku z 7 października; cytat poza kopią publiczną) → sovmil — niezależna kontrola (runda 3) dała TAK, ale zauważyła, że strona niepaństwowa słabo pasuje do definicji „geopolitical tensions between states” (bliżej `terror`).

| gold         |   fx_capital |   macro |   monetary |   sovmil |   trade_policy |
|:-------------|-------------:|--------:|-----------:|---------:|---------------:|
| fx_capital   |           10 |       1 |          0 |        0 |              0 |
| macro        |            0 |       6 |          0 |        0 |              0 |
| monetary     |            3 |       1 |          3 |        0 |              0 |
| sovmil       |            0 |       0 |          1 |        3 |              0 |
| trade_policy |            0 |       0 |          0 |        0 |              2 |


**Werdykt: validated = false** (bramka: E1, E2 z wariantem zamaskowanym, E4-hist; E3 to kontrola; wyniki: {'E1': False, 'E4-hist': False, 'E3 (kontrola)': '4/7', 'E2': True}).


## Diagnostyka wejścia E4-hist (po przebiegu, bez wpływu na wynik)

Każdy dzień: 600 pozycji (limit planu). Mediana liczby slugów zawierających słowo kluczowe zdarzenia wśród 600:

| typ dnia (wzorzec) | „fed” | „fomc” | „rate” | „opec” | „oil” | „hack” | „etf” |
|---|---|---|---|---|---|---|---|
| monetary (FOMC, 26) | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| oil_supply (OPEC, 12) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| crypto_hack (2) | 0,5 | 0 | 0 | 0 | 6 | 0 | 0 |
| crypto_etf (2) | 0 | 0 | 0,5 | 0 | 0 | 1 | 1,5 |

Ranking „max NumMentions” wypycha na górę największe tematy dnia (konflikty, polityka); artykuły o zdarzeniu kalendarza
nie mieszczą się w 600. Wynik 0/42 jest zgodny z zarejestrowanym planem, ale — jak w próbach 1–2 — mierzy dobór wejścia,
nie zdolność modelu. Odsetek par USA–USA wśród wybranych pozycji: mediana 0,18 (min 0,02, max 0,55) — filtr USA–USA
nie był przyczyną (nie był stosowany).
