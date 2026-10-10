# Walidacja analogii — 2026-10-06

Zapytania co 20 dni decyzji, ostatnie 10 lat (krypto: od kiedy są cechy i kandydaci). Prognoza p_up/p_down = częstość w 20 analogiach; fakt z tabeli labels (±1,5σ, 5 dni). Brier = średnia z up i down. BSS = 1 − Brier/Brier_bazowej. 95% CI: bootstrap blokowy (bloki po 6 zapytań, 2000 powtórzeń). Werdykt „lepsze” tylko gdy dolna granica CI BSS > 0.

Interpretacja: częstość w 20 datach ma wariancję p(1−p)/20, więc nawet trafne co do średniej analogie płacą karę w Brierze względem gładkiej częstości bazowej (wiersz „oczekiwany BSS samego szumu”). BSS gorszy niż ta kara = dodatkowo zła kalibracja (np. częstość w analogiach systematycznie wyższa niż fakt).

## Podsumowanie

| aktywo | zapytań | BSS analogie [95% CI] | BSS losowe | BSS szumu k=20 | werdykt |
|---|---|---|---|---|---|
| XAU | 125 | -0.019 [-0.104, +0.058] | -0.041 | -0.051 | **analogie nie lepsze od bazowej** |
| XAG | 125 | -0.019 [-0.087, +0.041] | -0.078 | -0.048 | **analogie nie lepsze od bazowej** |
| WTI | 112 | -0.057 [-0.107, -0.002] | -0.034 | -0.043 | **analogie gorsze od bazowej** |
| BRENT | 124 | -0.040 [-0.078, -0.004] | -0.044 | -0.044 | **analogie gorsze od bazowej** |
| BTC | 92 | -0.097 [-0.259, -0.032] | -0.145 | -0.064 | **analogie gorsze od bazowej** |
| ETH | 95 | -0.075 [-0.222, -0.015] | -0.086 | -0.057 | **analogie gorsze od bazowej** |

## XAU

Zapytań: 125 (2016-10-06 … 2026-09-03), pominiętych: 1 (za mało kandydatów albo brak etykiety). Najstarszy dopuszczalny kandydat: 2004-01-06 … 2004-01-06. Faktyczna częstość w zapytaniach: up 0.080, down 0.040; średnia prognoza analogii: up 0.075, down 0.070.

| metryka | wartość | 95% CI |
|---|---|---|
| Brier: analogie | 0.0573 | [0.0319, 0.0876] |
| Brier: losowe z tercyla rv_60d | 0.0586 | [0.0338, 0.0862] |
| Brier: częstość bazowa (tylko przeszłość) | 0.0563 | [0.0316, 0.0842] |
| BSS analogie vs bazowa | -0.0187 | [-0.1044, 0.0576] |
| BSS losowe vs bazowa | -0.0407 | [-0.0995, -0.0094] |
| BSS analogie − losowe | 0.0220 | [-0.0630, 0.1178] |
| oczekiwany BSS samego szumu próby k=20 (p(1−p)/k) | -0.0509 | [-0.0904, -0.0341] |
| Spearman: mediana 20d analogii vs fakt | 0.1100 | [-0.0775, 0.2817] |
| Spearman: mediana 20d losowych vs fakt | -0.0722 | [-0.2838, 0.1436] |
| Spearman: mediana 60d analogii vs fakt | 0.0312 | [-0.2293, 0.2803] |
| Spearman: mediana 60d losowych vs fakt | 0.0701 | [-0.1131, 0.2568] |

Werdykt: **analogie nie lepsze od bazowej** (BSS -0.019, 95% CI [-0.104, +0.058]); nie lepsze od losowych z tercyla.

_czas: 5 s_

## XAG

Zapytań: 125 (2016-10-06 … 2026-09-03), pominiętych: 1 (za mało kandydatów albo brak etykiety). Najstarszy dopuszczalny kandydat: 2004-01-06 … 2004-01-06. Faktyczna częstość w zapytaniach: up 0.072, down 0.056; średnia prognoza analogii: up 0.060, down 0.058.

| metryka | wartość | 95% CI |
|---|---|---|
| Brier: analogie | 0.0610 | [0.0362, 0.0852] |
| Brier: losowe z tercyla rv_60d | 0.0646 | [0.0384, 0.0898] |
| Brier: częstość bazowa (tylko przeszłość) | 0.0599 | [0.0351, 0.0844] |
| BSS analogie vs bazowa | -0.0185 | [-0.0869, 0.0412] |
| BSS losowe vs bazowa | -0.0783 | [-0.1484, -0.0226] |
| BSS analogie − losowe | 0.0598 | [-0.0033, 0.1196] |
| oczekiwany BSS samego szumu próby k=20 (p(1−p)/k) | -0.0484 | [-0.0824, -0.0344] |
| Spearman: mediana 20d analogii vs fakt | 0.0617 | [-0.0556, 0.1845] |
| Spearman: mediana 20d losowych vs fakt | -0.0846 | [-0.2649, 0.0903] |
| Spearman: mediana 60d analogii vs fakt | -0.0472 | [-0.2611, 0.1615] |
| Spearman: mediana 60d losowych vs fakt | -0.1139 | [-0.2628, 0.0331] |

Werdykt: **analogie nie lepsze od bazowej** (BSS -0.019, 95% CI [-0.087, +0.041]); nie lepsze od losowych z tercyla.

_czas: 5 s_

## WTI

Zapytań: 112 (2016-10-06 … 2026-09-03), pominiętych: 14 (za mało kandydatów albo brak etykiety). Najstarszy dopuszczalny kandydat: 2004-01-06 … 2004-01-06. Faktyczna częstość w zapytaniach: up 0.054, down 0.080; średnia prognoza analogii: up 0.035, down 0.061.

| metryka | wartość | 95% CI |
|---|---|---|
| Brier: analogie | 0.0659 | [0.0447, 0.0875] |
| Brier: losowe z tercyla rv_60d | 0.0646 | [0.0451, 0.0844] |
| Brier: częstość bazowa (tylko przeszłość) | 0.0624 | [0.0422, 0.0828] |
| BSS analogie vs bazowa | -0.0565 | [-0.1068, -0.0022] |
| BSS losowe vs bazowa | -0.0344 | [-0.1006, 0.0183] |
| BSS analogie − losowe | -0.0222 | [-0.0900, 0.0556] |
| oczekiwany BSS samego szumu próby k=20 (p(1−p)/k) | -0.0431 | [-0.0637, -0.0325] |
| Spearman: mediana 20d analogii vs fakt | -0.1404 | [-0.3046, 0.0605] |
| Spearman: mediana 20d losowych vs fakt | 0.0162 | [-0.2217, 0.2333] |
| Spearman: mediana 60d analogii vs fakt | -0.1571 | [-0.3527, 0.0591] |
| Spearman: mediana 60d losowych vs fakt | 0.0104 | [-0.2208, 0.2416] |

Werdykt: **analogie gorsze od bazowej** (BSS -0.057, 95% CI [-0.107, -0.002]); nie lepsze od losowych z tercyla.

_czas: 5 s_

## BRENT

Zapytań: 124 (2016-10-06 … 2026-09-03), pominiętych: 2 (za mało kandydatów albo brak etykiety). Najstarszy dopuszczalny kandydat: 2004-01-06 … 2004-01-06. Faktyczna częstość w zapytaniach: up 0.073, down 0.089; średnia prognoza analogii: up 0.053, down 0.080.

| metryka | wartość | 95% CI |
|---|---|---|
| Brier: analogie | 0.0772 | [0.0522, 0.1037] |
| Brier: losowe z tercyla rv_60d | 0.0775 | [0.0540, 0.1027] |
| Brier: częstość bazowa (tylko przeszłość) | 0.0743 | [0.0496, 0.0997] |
| BSS analogie vs bazowa | -0.0399 | [-0.0777, -0.0042] |
| BSS losowe vs bazowa | -0.0440 | [-0.1137, 0.0144] |
| BSS analogie − losowe | 0.0041 | [-0.0692, 0.0881] |
| oczekiwany BSS samego szumu próby k=20 (p(1−p)/k) | -0.0440 | [-0.0658, -0.0328] |
| Spearman: mediana 20d analogii vs fakt | -0.1230 | [-0.2960, 0.0349] |
| Spearman: mediana 20d losowych vs fakt | 0.0748 | [-0.1174, 0.2562] |
| Spearman: mediana 60d analogii vs fakt | 0.0909 | [-0.1269, 0.3120] |
| Spearman: mediana 60d losowych vs fakt | 0.1798 | [-0.0348, 0.4190] |

Werdykt: **analogie gorsze od bazowej** (BSS -0.040, 95% CI [-0.078, -0.004]); nie lepsze od losowych z tercyla.

_czas: 5 s_

## BTC

Zapytań: 92 (2021-09-05 … 2026-09-19), pominiętych: 75 (za mało kandydatów albo brak etykiety). Najstarszy dopuszczalny kandydat: 2018-09-06 … 2018-09-06. Faktyczna częstość w zapytaniach: up 0.054, down 0.033; średnia prognoza analogii: up 0.081, down 0.055.

| metryka | wartość | 95% CI |
|---|---|---|
| Brier: analogie | 0.0456 | [0.0214, 0.0750] |
| Brier: losowe z tercyla rv_60d | 0.0476 | [0.0234, 0.0769] |
| Brier: częstość bazowa (tylko przeszłość) | 0.0416 | [0.0176, 0.0705] |
| BSS analogie vs bazowa | -0.0971 | [-0.2587, -0.0320] |
| BSS losowe vs bazowa | -0.1455 | [-0.3842, -0.0535] |
| BSS analogie − losowe | 0.0484 | [-0.0801, 0.1993] |
| oczekiwany BSS samego szumu próby k=20 (p(1−p)/k) | -0.0644 | [-0.1524, -0.0379] |
| Spearman: mediana 20d analogii vs fakt | -0.0118 | [-0.2354, 0.1686] |
| Spearman: mediana 20d losowych vs fakt | -0.1007 | [-0.2714, 0.0533] |
| Spearman: mediana 60d analogii vs fakt | 0.0083 | [-0.2422, 0.2519] |
| Spearman: mediana 60d losowych vs fakt | -0.1004 | [-0.2463, 0.0795] |

Werdykt: **analogie gorsze od bazowej** (BSS -0.097, 95% CI [-0.259, -0.032]); nie lepsze od losowych z tercyla.

_czas: 4 s_

## ETH

Zapytań: 95 (2021-04-18 … 2026-09-19), pominiętych: 72 (za mało kandydatów albo brak etykiety). Najstarszy dopuszczalny kandydat: 2018-09-05 … 2018-09-06. Faktyczna częstość w zapytaniach: up 0.032, down 0.063; średnia prognoza analogii: up 0.052, down 0.079.

| metryka | wartość | 95% CI |
|---|---|---|
| Brier: analogie | 0.0486 | [0.0276, 0.0704] |
| Brier: losowe z tercyla rv_60d | 0.0491 | [0.0269, 0.0722] |
| Brier: częstość bazowa (tylko przeszłość) | 0.0452 | [0.0221, 0.0680] |
| BSS analogie vs bazowa | -0.0754 | [-0.2220, -0.0148] |
| BSS losowe vs bazowa | -0.0859 | [-0.2003, -0.0320] |
| BSS analogie − losowe | 0.0105 | [-0.0919, 0.1038] |
| oczekiwany BSS samego szumu próby k=20 (p(1−p)/k) | -0.0565 | [-0.1156, -0.0375] |
| Spearman: mediana 20d analogii vs fakt | -0.0682 | [-0.2204, 0.1033] |
| Spearman: mediana 20d losowych vs fakt | 0.0030 | [-0.1653, 0.1766] |
| Spearman: mediana 60d analogii vs fakt | -0.1716 | [-0.4431, 0.0729] |
| Spearman: mediana 60d losowych vs fakt | -0.1399 | [-0.3540, 0.0844] |

Werdykt: **analogie gorsze od bazowej** (BSS -0.075, 95% CI [-0.222, -0.015]); nie lepsze od losowych z tercyla.

_czas: 4 s_
