# Etap 4R — rejestr modeli (plan, 2026-10-06)

Każdy moduł (prob, przyszły dashboard) pyta `ms.registry.champion(con, aktywo, pytanie)` — żadnych modeli na sztywno.

## Pytania i metryki
- prob_up_5d / prob_down_5d: Brier, BSS vs częstość bazowa (osobno dla każdego kierunku).
- decomp_weekly: R² poza próbą (betas z t−1).
- event_response: zarezerwowane (GDELT), brak modeli.

## Interpretacje (do potwierdzenia)
- **Miesiąc oceny = miesiąc rozstrzygnięcia etykiety:** dzień D liczy się do miesiąca M, gdy jego okno 5 dni kończy
  się w M (end_5d ∈ M). Dzięki temu wynik za M nie używa żadnych danych po końcu M.
- **„Od teraz tylko miesiące poza próbą”:** mistrzów wybrano na okresie do 2026-10-06 (3A). Reguły awansu/degradacji
  biorą pod uwagę tylko miesiące zaczynające się po tej dacie (pierwszy: 2026-11). model_scores liczy się też dla
  wcześniejszych miesięcy (informacyjnie), ale reguły ich nie widzą. Pierwsza możliwa zmiana: po 6 takich miesiącach
  (ocena 2027-05-01).
- **Okno reguł:** 6 ostatnich pełnych, liczonych miesięcy; dzienne prognozy z tych miesięcy łączone razem; bootstrap
  blokowy (bloki 5 dni decyzji — długość okna etykiety), 2000 powtórzeń, ziarno stałe (deterministyczne).
- **Awans:** różnica BSS (pretendent − mistrz) na wspólnych dniach, dolna granica 95% CI > 0, n >= 100 dni;
  przy kilku kandydatach — największa różnica. Stary mistrz -> challenger.
- **Degradacja:** BSS mistrza vs częstość bazowa (fallback) z górną granicą CI < 0 -> mistrzem zostaje częstość bazowa.
- **decomp_weekly:** fallback = „brak dekompozycji” (wkłady 0, prognoza = średnia), R² poza próbą = 0 z definicji;
  degradacja, gdy górna granica CI R² mistrza < 0.
- **Rejestr jest dopisywany (append-only):** każda zmiana roli = nowy wiersz z since i niepustym reason; bieżąca rola =
  ostatni wiersz dla (aktywo, pytanie, model).
- **Odświeżanie prognoz przed oceną miesięczną:** eval_baselines -> train_gbm (note: monthly_refresh, ta sama konfiguracja)
  -> build_decomp -> eval_registry (tools/registry_monthly.sh, launchd 1. dnia miesiąca 06:00).
