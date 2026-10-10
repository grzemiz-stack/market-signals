# Etap 4A — dekompozycja tygodniowa i moduł prawdopodobieństwa (plan, 2026-10-06)

## Dekompozycja (src/ms/decompose.py)
- Koniec tygodnia: piątek 22:00 UTC (metale, ropa); krypto: niedziela 24:00 UTC (= poniedziałek 00:00).
- Zwrot tygodnia = log(cena ostatnio znana na koniec tygodnia / cena ostatnio znana na koniec poprzedniego); NaN, gdy
  w tygodniu jest logret NaN (WTI 2020-04-20).
- Czynniki = zmiany współbieżne, wartości jak znane na koniec tygodnia (panel_asof; okienkowe z pierwszych publikacji):
  koszt_alternatywny: Δ DFII10, zwrot koszyka dolara GRAM (EUR, JPY, CNY, AUD), Δ T10YIE;
  ryzyko: Δ VIX, Δ GPR (średnia 7d), Δ implied vol aktywa (XAU GVZ, WTI/BRENT OVX, BTC/ETH DVOL; XAG — brak, pominięte);
  momentum_pozycje: zwrot 4 tygodni przed (t−4..t−1), Δ COT net/OI;
  ropa_podaz (WTI, BRENT): niespodzianka zapasów = zmiana WPSR − średnia zmiana z tego tygodnia w 5 poprzednich latach
  (raport opublikowany w tygodniu; brak raportu = 0);
  krzyżowe: zwrot WTI (dla metali). Nasdaq/akcje — brak serii w bazie, pominięte (bez nowego źródła).
- OLS ze stałą na oknie 260 tygodni kończącym się w t−1; czynnik wchodzi, gdy ma wartość w t i >= 156 tygodni w oknie;
  okno >= 104 kompletne tygodnie. Wkład = beta × Δczynnik (suma po grupach); niewyjaśnione = zwrot − suma wkładów
  (zawiera stałą). t-stat: klasyczny błąd OLS.
- R² poza próbą: 1 − Σ(y − ŷ)² / Σ(y − ȳ) w danym okresie, ŷ = stała + suma wkładów z betami z t−1.
  R² w próbie: średnie R² regresji w oknach użytych w danym okresie.

## Moduł prawdopodobieństwa (src/ms/prob.py)
- Model = najlepszy z 3A per aktywo (tabela baseline_eval, wariant „wszystkie”), prognoza z baseline_preds.
- X% = 1,5σ (σ = std 252 dziennych logret do ostatniego znanego zamknięcia × √5), w górę exp(1,5σ)−1, w dół 1−exp(−1,5σ).
