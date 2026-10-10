# Etap 5 — portfel regułowy: część rozwojowa 2016-10-06 … 2024-10-05 (1000 zł)

> **Ostrzeżenia.** (1) Wynik backtestu NIE uprawnia do prawdziwych pieniędzy (D11). (2) Liczba prób w tej rodzinie: **N = 12** (8 momentum z 4P + równy podział + 3 warianty) — Deflated Sharpe to uwzględnia. (3) Sharpe z backtestu na żywo spada zwykle 2–4× (ZASADY cz. 4) — patrz kolumny „po cięciu”. (4) BTC/ETH wchodzą do portfela dopiero ~2018-08 (ceny od 2017-08-17), wcześniej portfel = XAG + WTI.

Reguły zamrożone przed liczeniem: prerejestracja `d9cb3a3a2da04caa` w runs. Dane odłożone (2024-10-06 … 2026-10-05) nie były liczone.

## Wynik (koszty jak 4P)

| wariant | na rękę | zwrot roczny | Sharpe | po cięciu 2× / 3× / 4× | t | Deflated Sharpe | maks. obsunięcie | najdłużej pod kreską | najgorszy miesiąc | najgorszy rok | rebalanse | koszty | podatek |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| iv_bez_filtra | 3 300 zł | +16,1% | 0,69 | 0,34 / 0,23 / 0,17 | 1,94 | 0,854 | -45,9% | 901 dni | -27,1% | -19,6% | 60 | 115 zł | 536 zł |
| iv_filtr | 2 115 zł | +9,8% | 0,57 | 0,29 / 0,19 / 0,14 | 1,62 | 0,801 | -29,6% | 1056 dni | -8,0% | -13,8% | 88 | 185 zł | 300 zł |
| iv_filtr_ovx | 2 162 zł | +10,1% | 0,60 | 0,30 / 0,20 / 0,15 | 1,71 | 0,824 | -27,8% | 1056 dni | -7,4% | -11,9% | 88 | 189 zł | 309 zł |
| rowny_podzial_4 | 9 076 zł | +31,8% | 0,86 | 0,43 / 0,29 / 0,22 | 2,44 | 0,948 | -59,5% | 925 dni | -29,2% | -45,3% | 33 | 255 zł | 1 895 zł |
| lokata | 1 130 zł | +1,5% | — | — / — / — | — | — | +0,0% | 0 dni | +0,0% | +0,1% | 0 | 0 zł | 0 zł |
| kup_i_trzymaj_XAU | 1 921 zł | +8,5% | 0,70 | 0,35 / 0,23 / 0,18 | 1,98 | 0,866 | -16,7% | 797 dni | -10,7% | -5,7% | 1 | 19 zł | 213 zł |
| momentum_1m | 1 646 zł | +6,4% | 0,36 | 0,18 / 0,12 / 0,09 | 1,00 | 0,560 | -75,4% | 1085 dni | -37,7% | -34,2% | 68 | 1 870 zł | 395 zł |

Sharpe = miesięczne zwroty konta w PLN ponad lokatę, w skali roku. t = Sharpe × √lat (próg z ZASAD: t > 3). Deflated Sharpe ≥ 0,95 = wynik odróżnialny od najlepszego z N prób bez przewagi. Na rękę = po sprzedaży wszystkiego i podatku za ostatni rok.

## Koszty ×2

| wariant | na rękę | zwrot roczny | Sharpe | maks. obsunięcie | koszty |
|---|---|---|---|---|---|
| iv_bez_filtra | 3 142 zł | +15,4% | 0,67 | -45,9% | 222 zł |
| iv_filtr | 1 894 zł | +8,3% | 0,50 | -31,6% | 348 zł |
| iv_filtr_ovx | 1 935 zł | +8,6% | 0,52 | -29,9% | 354 zł |
| rowny_podzial_4 | 8 554 zł | +30,8% | 0,85 | -59,7% | 488 zł |
| lokata | 1 130 zł | +1,5% | — | +0,0% | 0 zł |
| kup_i_trzymaj_XAU | 1 900 zł | +8,4% | 0,70 | -16,7% | 38 zł |
| momentum_1m | 696 zł | -4,4% | 0,16 | -82,2% | 2 369 zł |

## Przeuczenie wyboru (PBO)

PBO = **0,271** (70 podziałów CSCV, 8 bloków po ~12 mies., 12 kandydatów). Próg z ZASAD: < 0,5. Przy 12 kandydatach PBO jest zgrubne. Oczekiwany najlepszy Sharpe z N prób bez przewagi (SR*): 0,30 rocznie.

## Stabilność w czasie (okna 2-letnie, ta sama ścieżka konta)

| wariant | 2016-10…2018-10 | 2018-10…2020-10 | 2020-10…2022-10 | 2022-10…2024-10 |
|---|---|---|---|---|
| iv_bez_filtra | Sharpe -0,21, obs. -23,8% | Sharpe 0,68, obs. -45,9% | Sharpe 1,46, obs. -29,9% | Sharpe 0,31, obs. -20,5% |
| iv_filtr | Sharpe 0,24, obs. -16,9% | Sharpe 0,40, obs. -25,9% | Sharpe 1,55, obs. -19,1% | Sharpe -0,29, obs. -15,9% |
| iv_filtr_ovx | Sharpe 0,25, obs. -17,4% | Sharpe 0,33, obs. -26,4% | Sharpe 1,62, obs. -19,6% | Sharpe -0,26, obs. -15,1% |
| rowny_podzial_4 | Sharpe 0,52, obs. -42,6% | Sharpe 0,73, obs. -50,1% | Sharpe 1,46, obs. -38,0% | Sharpe 0,61, obs. -24,6% |
| kup_i_trzymaj_XAU | Sharpe -0,33, obs. -16,1% | Sharpe 2,02, obs. -10,8% | Sharpe 0,46, obs. -15,3% | Sharpe 0,56, obs. -12,3% |
| momentum_1m | Sharpe 0,61, obs. -57,3% | Sharpe 0,15, obs. -67,5% | Sharpe 0,96, obs. -52,4% | Sharpe -0,81, obs. -51,6% |

## Podokres z kompletem 4 aktywów (2018-09 … 2024-10-05)

| wariant | zwrot roczny | Sharpe | maks. obsunięcie |
|---|---|---|---|
| iv_bez_filtra | +24,5% | 0,85 | -45,9% |
| iv_filtr | +13,3% | 0,66 | -29,6% |
| iv_filtr_ovx | +13,8% | 0,70 | -27,8% |
| rowny_podzial_4 | +39,0% | 0,95 | -50,1% |
| lokata | +1,9% | — | +0,0% |
| kup_i_trzymaj_XAU | +15,0% | 0,98 | -16,7% |
| momentum_1m | +3,4% | 0,30 | -75,4% |

## Zwycięzca wg reguły D7 (ustalonej przed wynikami)

- iv_filtr vs iv_bez_filtra: Sharpe nie wyższy, obsunięcie nie gorsze -> zostaje iv_bez_filtra
- iv_filtr_ovx vs iv_bez_filtra: Sharpe nie wyższy, obsunięcie nie gorsze -> zostaje iv_bez_filtra
- iv_bez_filtra vs rowny_podzial_4: koszty x1 NIE lepszy, koszty x2 NIE lepszy
- -> konto system wykonuje rowny_podzial_4

**Konto „system” będzie wykonywać: `rowny_podzial_4`** (po jednorazowym otwarciu danych odłożonych — krok 4).

## Uwagi

- V3: σ ropy z OVX w 100% decyzji (reszta: σ z historii — brak OVX/k albo za krótka historia ilorazu).
- **Ograniczenie wyceny ropy:** ETC ropy wyceniane ruchem ceny spot WTI (jak 4P). Prawdziwe ETC tracą na rolowaniu kontraktów (ZASADY cz. 2: USO vs BNO), a 2020-04-20 spot był ujemny (−36,98 USD; wycena obcięta do 0 — jednodniowy spadek konta, odrobiony w 3 dni). Warianty inverse-vol trzymają więcej ropy niż równy podział, więc to uproszczenie może je zawyżać bardziej. Nie zmieniane po zobaczeniu wyników.
- Okna 2-letnie i podokres liczone na tej samej ścieżce konta (bez restartu); koszty i podatek jak w całości.
- Uproszczenia jak w 4P: ETF/ETC wyceniane ruchem spot, podatek do potwierdzenia u doradcy (src/ms/tax.py).
