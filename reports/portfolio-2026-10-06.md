# Portfel — PRZYKŁAD (fikcyjny) — 2026-10-06

> **To jest portfel przykładowy, fikcyjny** — pozycje i ceny zakupu wymyślone na potrzeby raportu.
> Zasady podatkowe: do potwierdzenia u doradcy (to nie jest porada podatkowa). Zasady: src/ms/tax.py.

Wycena: spot USD (ms.prices) × USD/PLN (NBP, ostatnia tabela <= dzień wyceny). Złoto fizyczne „na rękę” = spot × (1 − dyskonto skupu). ETF: brak notowań w bazie — przybliżenie ruchem spot złota od dnia zakupu.

## Pozycje

|   id | asset   | form          | ticker               |   quantity | unit      |   buy_price | currency   | buy_date            |   buyback_discount_pct | note                                                              |
|-----:|:--------|:--------------|:---------------------|-----------:|:----------|------------:|:-----------|:--------------------|-----------------------:|:------------------------------------------------------------------|
|    1 | XAU     | sztabka       | nan                  |        2   | szt       |     11954.9 | PLN        | 2025-03-15 00:00:00 |                      3 | PRZYKŁAD (fikcyjny): 2 sztabki 1 oz, cena = spot × kurs × 1,04    |
|    2 | XAU     | etf           | ETF-ZŁOTO (przykład) |       50   | jednostki |        30   | USD        | 2025-03-17 00:00:00 |                      3 | PRZYKŁAD (fikcyjny): ETF na złoto, wycena przybliżona ruchem spot |
|    3 | BTC     | krypto_gielda | nan                  |        0.1 | jednostki |     84507.1 | USD        | 2025-03-15 00:00:00 |                      3 | PRZYKŁAD (fikcyjny): 0,1 BTC                                      |

## Wycena i rozbicie wyniku (PLN)

| id | forma | rynkowa | na rękę | koszt | cena USD | kurs USD/PLN | koszty wejścia | koszty wyjścia | przechowanie | wynik | podatek | po podatku |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | sztabka XAU | 32 187 | 31 221 | 23 910 | 8 899 | 297 | -920 | -966 | 0 | 7 311 | 0 | 7 311 |
| 2 | etf XAU | 8 084 | 8 060 | 5 796 | 2 195 | 112 | -19 | -23 | 0 | 2 265 | 440 | 1 825 |
| 3 | krypto_gielda BTC | 33 336 | 33 269 | 32 551 | 550 | 308 | -73 | -67 | 0 | 719 | 177 | 542 |
| **razem** | | 73 606 | 72 550 | 62 256 | 11 644 | 717 | -1 012 | -1 056 | 0 | 10 294 | 617 | 9 678 |

Wynik = cena USD + kurs USD/PLN + koszty wejścia + koszty wyjścia + przechowanie (suma dokładna). „Po podatku” = wynik przy hipotetycznej sprzedaży dziś.

## Podatek per pozycja (do potwierdzenia u doradcy)

- id 1 (sztabka XAU): złoto fizyczne: zwolnione od 2025-10-01; podatek przy sprzedaży dziś: 0 PLN
- id 2 (etf XAU): ETF: 19% od dochodu; podatek przy sprzedaży dziś: 440 PLN
- id 3 (krypto_gielda BTC): krypto: 19% od nadwyżki przychodów nad kosztami (z przeniesieniem); podatek przy sprzedaży dziś: 177 PLN

## Koszt zamiany (przykłady)

- Zamiana sztabka XAU (id 1) -> etf: koszt 1 056 PLN (wyjście 966, podatek 0, wejście 90). Zamiana opłaca się, jeśli B zyska względem A ponad 3,39%.
- Zamiana sztabka XAU (id 1) -> krypto_gielda: koszt 1 028 PLN (wyjście 966, podatek 0, wejście 62). Zamiana opłaca się, jeśli B zyska względem A ponad 3,30%.
- Zamiana krypto_gielda BTC (id 3) -> sztabka: koszt 1 207 PLN (wyjście 67, podatek 177, wejście 964). Zamiana opłaca się, jeśli B zyska względem A ponad 3,76%.

Założenia kosztów: prowizje/premie domyślne w ms.portfolio (EXIT_FEE_PCT, ENTRY_PREMIUM_PCT); próg liczony względem wartości rynkowej A (pełne tarcie zamiany).

## Szoki ręczne (na rękę, przed podatkiem)

| scenariusz | zmiana PLN | zmiana % |
|---|---|---|
| złoto −10% | -3 928 | -5,4% |
| USD/PLN −5% | -3 628 | -5,0% |
| BTC −30% | -9 981 | -13,8% |
| razem: złoto −10%, USD/PLN −5%, BTC −30% | -16 841 | -23,2% |

## Scenariusze historyczne (faktyczne łączne ruchy zastosowane do obecnego portfela)

| okres | ruchy aktywów (USD) | USD/PLN | zmiana PLN | zmiana % | uwagi |
|---|---|---|---|---|---|
| 2008-09…2008-11 (kryzys finansowy) | BTC brak, XAU -1,5% | +28,7% | 20 047 | +27,6% | brak historii: BTC — przyjęto 0% zmiany ceny w USD (kurs USD/PLN nadal działa) |
| 2013-04 (krach złota) | BTC brak, XAU -7,5% | -2,7% | -4 818 | -6,6% | brak historii: BTC — przyjęto 0% zmiany ceny w USD (kurs USD/PLN nadal działa) |
| 2020-03 (COVID) | BTC -24,8%, XAU -0,1% | +5,6% | -4 686 | -6,5% |  |
| 2022-03…2022-10 (podwyżki stóp) | BTC -52,5%, XAU -14,5% | +12,8% | -16 829 | -23,2% |  |

## Skupienie ryzyka (dzienne zwroty w PLN, 1 rok)

Korelacje:

|                     |   1:sztabka XAU |   2:etf XAU |   3:krypto_gielda BTC |
|:--------------------|----------------:|------------:|----------------------:|
| 1:sztabka XAU       |            1    |        1    |                  0.31 |
| 2:etf XAU           |            1    |        1    |                  0.31 |
| 3:krypto_gielda BTC |            0.31 |        0.31 |                  1    |

Udział w wariancji portfela:

|                     |   udział |
|:--------------------|---------:|
| 1:sztabka XAU       |     0.31 |
| 2:etf XAU           |     0.08 |
| 3:krypto_gielda BTC |     0.61 |

Największe ryzyko: **3:krypto_gielda BTC** — 61% wariancji portfela przy 46% wartości portfela.
