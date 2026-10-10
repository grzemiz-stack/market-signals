# Etap 5 — dane odłożone 2024-10-06 … 2026-10-05 (1000 zł od nowa)

> **Jedyne otwarcie** (wpis `5-holdout` w runs przed liczeniem; reguły `d9cb3a3a2da04caa`). Zwycięzca wybrany regułą D7 na części rozwojowej PRZED otwarciem: **`rowny_podzial_4`**. Po otwarciu żadnych zmian reguł. Wynik NIE uprawnia do prawdziwych pieniędzy (D11).

> **Te 2 lata nie są dziewicze (D8):** backtest 4P (równy podział, momentum) i wybór mistrza OVX w 3A objęły ten okres. Nowe warianty V1–V3 nie były na nim liczone. Czysty test = konta „system” od 2026-10-07.

## Wynik (koszty jak 4P) — obok część rozwojowa

| wariant | na rękę | zwrot roczny | Sharpe | Sharpe (rozwój) | maks. obsunięcie | obsunięcie (rozwój) | próg wyłączenia D9 | najgorszy miesiąc | rebalanse | koszty | podatek |
|---|---|---|---|---|---|---|---|---|---|---|---|
| iv_bez_filtra | 1 673 zł | +29,4% | 0,98 | 0,69 | -29,0% | -45,9% | -68,8% | -19,3% | 18 | 39 zł | 157 zł |
| iv_filtr | 1 450 zł | +20,5% | 0,99 | 0,57 | -21,6% | -29,6% | -44,4% | -13,8% | 24 | 38 zł | 101 zł |
| iv_filtr_ovx | 1 401 zł | +18,4% | 0,96 | 0,60 | -22,1% | -27,8% | -41,6% | -14,3% | 25 | 38 zł | 90 zł |
| **rowny_podzial_4** | 1 555 zł | +24,7% | 0,81 | 0,86 | -32,5% | -59,5% | -89,2% | -18,9% | 9 | 31 zł | 129 zł |
| lokata | 1 061 zł | +3,0% | — | — | +0,0% | +0,0% | — | +0,0% | 0 | 0 zł | 0 zł |
| kup_i_trzymaj_XAU | 1 437 zł | +19,9% | 1,09 | 0,70 | -22,0% | -16,7% | -25,0% | -8,7% | 1 | 15 zł | 102 zł |
| momentum_1m | 2 737 zł | +65,6% | 1,12 | 0,36 | -39,7% | -75,4% | nieosiągalny (> 100%) | -22,4% | 16 | 365 zł | 413 zł |

Próg wyłączenia D9 = 1,5 × najgorsze obsunięcie z części rozwojowej (dla kont „system”).

## Koszty ×2

| wariant | na rękę | zwrot roczny | Sharpe | maks. obsunięcie |
|---|---|---|---|---|
| iv_bez_filtra | 1 632 zł | +27,8% | 0,95 | -29,0% |
| iv_filtr | 1 412 zł | +18,9% | 0,93 | -21,8% |
| iv_filtr_ovx | 1 364 zł | +16,8% | 0,90 | -22,3% |
| rowny_podzial_4 | 1 523 zł | +23,5% | 0,79 | -32,7% |
| lokata | 1 061 zł | +3,0% | — | +0,0% |
| kup_i_trzymaj_XAU | 1 422 zł | +19,3% | 1,07 | -22,0% |
| momentum_1m | 2 251 zł | +50,2% | 0,95 | -43,6% |

## Okna roczne (ta sama ścieżka konta)

| wariant | 2024-10…2025-10 | 2025-10…2026-10 |
|---|---|---|
| iv_bez_filtra | Sharpe 0,92, zwrot +25,2%, obs. -24,8% | Sharpe 0,97, zwrot +42,9%, obs. -29,0% |
| iv_filtr | Sharpe 1,19, zwrot +22,1%, obs. -14,1% | Sharpe 0,84, zwrot +25,5%, obs. -21,6% |
| iv_filtr_ovx | Sharpe 1,14, zwrot +20,7%, obs. -14,3% | Sharpe 0,80, zwrot +22,3%, obs. -22,1% |
| rowny_podzial_4 | Sharpe 1,06, zwrot +45,8%, obs. -32,5% | Sharpe 0,44, zwrot +13,6%, obs. -27,9% |
| kup_i_trzymaj_XAU | Sharpe 1,90, zwrot +34,6%, obs. -8,7% | Sharpe 0,49, zwrot +12,2%, obs. -22,0% |
| momentum_1m | Sharpe 0,46, zwrot +19,1%, obs. -39,7% | Sharpe 1,57, zwrot +158,4%, obs. -36,9% |

## Reguła D7 zastosowana do danych odłożonych (tylko informacja — wyboru to nie zmienia)

- iv_filtr vs iv_bez_filtra: Sharpe wyższy, obsunięcie nie gorsze -> awans
- iv_filtr_ovx vs iv_filtr: Sharpe nie wyższy, obsunięcie gorsze -> zostaje iv_filtr
- iv_filtr vs rowny_podzial_4: koszty x1 lepszy, koszty x2 lepszy

## Uwagi

- 24 miesiące to mało: Sharpe z 2 lat ma błąd standardowy ok. ±0,8 (przy Sharpe ~0,9) — różnice między wariantami w tej tabeli są w granicach szczęścia. Deflated Sharpe i PBO nie są tu liczone (za krótki okres).
- Wycena ropy spotem (jak 4P i część rozwojowa) — ograniczenie opisane w raporcie części rozwojowej.
- Każdy przebieg zaczyna od 1000 zł 2024-10-06 (σ i trend z historii sprzed startu).
