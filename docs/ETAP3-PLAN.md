# Etap 3 — punkty odniesienia ze zmienności (3A) i LightGBM (3B) — plan 2026-10-06

## Wspólna rama (3A i 3B)
- Cel: up_5d / down_5d z labels (suma logret D+1..D+5 vs ±1,5·sigma_5d, sigma_5d = std 252 obs × √5 do D).
- **Czas:** prognoza dnia D powstaje w chwili decyzji D 22:00 UTC (jak cechy). Ostatnie znane zamknięcie L(D) =
  ostatnia obserwacja ceny z known_at <= D 22:00 (krypto: zwykle D−1, bo świeca D zamyka się o 00:00 UTC;
  od 2026-10-06 ceny rynkowe mają known_at = zamknięcie sesji, więc dla metali i ropy zwykle L = D, g = 0).
  Luka g = pozycja(D) − pozycja(L).
  Model prognozuje sumę zwrotów kroków g+1..g+5 od L (= D+1..D+5). Bez tego perturbacja przyszłości (3B) by padła.
- **Walk-forward:** foldy testowe = lata kalendarzowe; okno treningowe rozszerzane, refit co rok (GARCH co miesiąc).
  Purge: z treningu wypadają próbki z end_5d >= początek foldu. Embargo 40 dni: trening kończy się
  >= 40 dni przed początkiem foldu (w czystym walk-forward „do przodu” to luka bezpieczeństwa, nie usuwanie po teście).
- **Częstość bazowa** w D: średnia up_5d/down_5d z etykiet z end_5d < D (tylko przeszłość).
- **Ewaluacja:** (1) zapytania co 20 dni decyzji, 10 lat, bootstrap blokowy po 6 zapytań; (2) WSZYSTKIE dni, 10 lat,
  bootstrap blokami 60 dni kalendarzowych. Brier = średnia z up i down, BSS = 1 − Brier/Brier_bazowej, 2000 powtórzeń.
- **Najlepszy punkt odniesienia per aktywo:** najwyższy BSS na wszystkich dniach; raport mówi, czy jego CI > 0.

## Modele 3A
a) rv-ratio: logistyczna p ~ log(rv20/σ252) + log(rv5/σ252) (dzienne std), osobno up i down.
b) GARCH(1,1)-t (arch), refit co miesiąc (dane do D), symulacja 2000 ścieżek, P(suma kroków g+1..g+5 > ±1,5·sigma_5d).
c) HAR-RV na r² (brak danych śróddziennych): średnia wariancja 5 dni ~ RV_d + RV_w + RV_m (OLS, walk-forward),
   σ̂_5d = √(5·v̂); rozkład t dopasowany na resztach standaryzowanych (zwrot 5d / σ̂_5d) z treningu.
d) Implied vol: XAU→GVZ, WTI/BRENT→OVX, BTC/ETH→DVOL; XAG — brak indeksu (pominięte).
   σ_5d = IV/100 × √(5/252) (krypto: DVOL liczony na 365 dni -> √(5/365)); p z N(0, σ). Wersja skalibrowana:
   sigmoid (Platt) na logit(p) walk-forward z purge/embargo.

## 3B — decyzje implementacyjne
- Cecha „punkt odniesienia”: wybór per fold z przeszłości (najniższy Brier na OOS sprzed foldu, purge+embargo;
  bez historii: rv_ratio). Werdykt porównuje z najlepszym modelem z 3A (wybranym na teście) — ostrożnie dla LightGBM.
- Test „brak próbki z path_end >= start foldu” interpretowany jako koniec okna etykiety (end_5d): przy celu 5-dniowym
  i embargo 40 dni literalne path_end (60 obs) przeczyłoby „purge 5 dni”.
- Wczesne zatrzymanie: ostatnie 2 lata treningu (z własnym purge/embargo) jako walidacja, potem refit na całym treningu
  z najlepszą liczbą rund (min 10; bez danych walidacyjnych: 100, zapisane w metadanych).
- Determinizm: LightGBM deterministic=True; GARCH: ziarno w StudentsT (arch ignoruje random_state dla simulation).
- SHAP: masker Independent z max_samples=500 (domyślnie shap obcina tło do 100).

## Poprawka PIT cen rynkowych (2026-10-06, po pierwszym 3A/3B)
Ceny rynkowe są publiczne w dniu notowania: EIA RWTC/RBRTE known_at = D 14:30 ET (settlement; 18:30/19:30 UTC),
Stooq = D 17:00 ET (koniec dnia handlowego NY; potwierdzone brakiem słupków niedzielnych od 1990), Yahoo = D 17:00 ET,
Binance bez zmian (zamknięcie świecy). Flaga known_at_market_close. Opóźnienie publikacji zostaje dla danych
powstających w chwili publikacji (WPSR, COT, FRED makro, GPR/TPU). 3A powtórzone: modele cenowe ropy +0,003…+0,007 BSS,
implied vol bez zmian. 3B i walidacja analogii powtórzone na nowych regułach (runs: note = rerun_after_pit_fix,
ta sama konfiguracja); raporty z 2026-10-06 zastąpione.
