# Etap 5 — portfel regułowy (PLAN, bez kodu)

Stan: 2026-10-07, **do akceptacji**. Podstawa: docs/ZASADY-INWESTOWANIA.md, sekcja „Co z tego wynika dla market-signals”
(oraz części 3 i 4). Zasada nadrzędna: **wszystkie warianty i reguły ustalone przed pierwszym przeliczeniem; żadnych
zmian po zobaczeniu wyników na danych odłożonych.**

---

## 1. Cel i czego ten etap NIE robi

- Cel: sprawdzić, czy prosta reguła ryzyka (wagi odwrotnie do zmienności + wolny filtr trendu) daje lepszy stosunek
  zysku do obsunięcia niż równy podział — i jeśli tak, wykonywać ją automatycznie na koncie „system” obok konta „gra 1”.
- Nie robi: prognoz zwrotu, optymalizacji wag, dobierania okien pod wynik, nowych źródeł danych. Wagi nie korzystają
  z żadnej prognozy kierunku (ZASADY 3.1). Jedyny model w regule to prognoza zmienności ropy (mistrz z rejestru).

## 2. Aktywa, okres, wykonanie (jak w 4P)

- **Aktywa portfela: BTC, ETH, XAG, WTI** (`GAME_ASSETS` z ms.trading — te same co w grze i w backteście 4P, żeby
  porównanie z równym podziałem i momentum było jabłka do jabłek). Złoto (XAU) tylko jako punkt odniesienia — patrz D1.
- **Okres:** 10 lat jak w 4P, koniec = ostatni wspólny dzień danych (dziś 2026-10-05).
  - **część rozwojowa:** 2016-10-06 … 2024-10-05 (8 lat),
  - **część odłożona:** 2024-10-06 … 2026-10-05 (ostatnie 2 lata) — otwierana **raz** (pkt 6).
  **Uwaga (sprawdzone w bazie):** ceny BTC i ETH w `price_frame` zaczynają się 2017-08-17 (XAG 1964, WTI 1986).
  Krypto wchodzi do portfela dopiero po 250 dniach σ i 12 mies. trendu, czyli ok. **2018-08**. Do tego czasu portfel
  = XAG + WTI (tak samo było w 4P: aktywo bez historii nie startuje). Część rozwojowa z pełnym zestawem 4 aktywów
  to więc ~6 lat, nie 8 — patrz D10.
- **Wykonanie, koszty, podatek, gotówka: bez zmian z 4P** (ms.trading.Costs i Account): decyzja z danych znanych
  w D 22:00 UTC, wykonanie po zamknięciu następnego dnia roboczego USA (wszystkie aktywa naraz), przewalutowanie 0,5%
  przy każdej konwersji, spread 0,1%, krypto 0,1% prowizji, ETF/ETC 0%; gotówka = stopa ref. NBP − 1 pp po Belce;
  podatek 19% rozliczany 31.12 (krypto osobną pulą); wynik „na rękę po likwidacji”. ETF/ETC wyceniane ruchem spot
  (przybliżenie — jak w 4P).

## 3. Reguły (ustalone z góry)

Dzień decyzji = **ostatni dzień roboczy USA miesiąca** (`momentum.rebalance_dates(..., "M")`). Wszystko liczone tylko
z cen znanych w D 22:00 (`PriceBook.known_close`), w USD.

**R1. Zmienność (σ).** Dzienne log-zwroty z dni notowań, σ_60 i σ_250 (odchylenie standardowe, w skali roku: √252 dla
XAG/WTI, √365 dla krypto). **σ_i = średnia z σ_60 i σ_250** (D2). Tylko przeszłość — okno kończy się na ostatnim
zamknięciu znanym w D 22:00.

**R2. Wagi inverse-vol z sufitem.** w_i = (1/σ_i) / Σ(1/σ_j). **Sufit: BTC + ETH razem ≤ 25% kapitału**; nadwyżkę
rozdziela się na XAG i WTI proporcjonalnie do ich wag (D3). Aktywo bez pełnych 250 dni historii nie wchodzi.

**R3. Filtr trendu (wolny).** Dla każdego aktywa zwrot ceny za **3, 6, 9 i 12 miesięcy** (jak `momentum.signal`, z cen
znanych w D). **Ekspozycja e_i = odsetek okien z dodatnim zwrotem** (0; 0,25; 0,5; 0,75; 1) — D4. Docelowa waga
= w_i × e_i; reszta (Σ w_i × (1 − e_i)) leży na lokacie. Sygnał liczony raz w miesiącu.

**R4. Ropa skalowana prognozą zmienności z OVX (D5, zmienione 2026-10-07).** W wariancie V3 σ_WTI z R1 zastępuje
**σ_OVX = OVX_D / 100 × k_D**:
- OVX_D = ostatnia wartość FRED.OVXCLS znana w D 22:00 (`as_of`, known_at 16:15 ET dnia notowania);
- k_D = **mediana z 3 lat wstecz (756 dni notowań) ilorazu σ zrealizowana w kolejnych 21 dniach / OVX**, tylko z dni t,
  dla których całe 21-dniowe okno skończyło się do ostatniego zamknięcia WTI znanego w D (żadnej wiedzy z przyszłości).
  To korekta premii za zmienność (od 2010 OVX ≈ 1,18 × późniejsza zmienność zrealizowana; sprawdzone 2026-10-07 na całej
  historii jako opis zjawiska, nie wynik strategii). To **nowa kalibracja etapu 5**, nie kalibracja z 3A (ta istnieje
  tylko dla prawdopodobieństw p_up/p_down i nie daje σ).
- Rejestr: V3 używa σ_OVX, dopóki mistrz WTI dla `prob_down_5d` (`registry.champion`) jest modelem na OVX
  (`iv_raw` albo `iv_calibrated`; dziś `iv_calibrated`). Gdy mistrzem zostanie inny model albo fallback, albo brak OVX
  lub k_D (mniej niż 756 dni historii ilorazu) → σ_WTI z R1. Źródło σ zapisywane w migawce decyzji.

**R5. Rebalans.** W dniu decyzji transakcje wykonuje się, gdy zachodzi któreś (D6):
(a) koniec kwartału (marzec, czerwiec, wrzesień, grudzień), albo
(b) bieżąca waga któregoś aktywa odchyla się od docelowej o więcej niż **±25% względnie** (|w_bież / w_doc − 1| > 0,25;
    dla w_doc = 0: jakakolwiek pozycja > 0 — czyli wyjście z trendu wykonuje się od razu), albo
(c) zmieniła się ekspozycja trendu e_i któregoś aktywa.
Wtedy cały portfel wraca do wag docelowych; tylko różnice (sprzedaż przed kupnem, jak `run_equal_weight`).
Pomijane zlecenia < 1% kapitału (koszt przewalutowania przy groszowych korektach).

## 4. Warianty i porównania — lista zamknięta (każdy = osobna próba w `runs`, stage `5`)

| id | nazwa | reguły |
|---|---|---|
| V1 | `iv_bez_filtra` | R1, R2, R5(a, b) — zawsze w pełni zainwestowany |
| V2 | `iv_filtr` | R1, R2, R3, R5 |
| V3 | `iv_filtr_ovx` | R1, R2, R3, R4, R5 |
| B1 | `rowny_podzial_4` | istniejący `run_equal_weight` (rebalans kwartalny) |
| B2 | `lokata` | istniejący `run_deposit` |
| B3 | `kup_i_trzymaj_XAU` | istniejący `run_buy_hold("XAU")` |
| B4 | `momentum_1m` | istniejący `run_momentum("1m", False)` — porównanie gry 1 |

- **Każdy z 7 przebiegów liczony też przy kosztach ×2** (prowizje, przewalutowanie, spread i próg prowizji ETF ×2;
  lokata i podatek bez zmian) — 14 wierszy w `runs`. Wersja ×2 to test wrażliwości, nie nowy kandydat: nie zwiększa N.
- W `runs.params` pełna definicja (okna, sufit, progi, aktywa, okres, Costs) i jej hash. **Zmiana czegokolwiek = nowa
  próba**, nie rerun (zasada z 4H).
- **Wstecznie dopisuję do `runs` 11 przebiegów 4P** (8 wariantów momentum + 3 odniesienia) z notą „dopisane w etapie 5,
  liczone 2026-10-06” — dziś ich nie ma w `runs`, a liczą się do liczby prób.
- **Liczba prób do Deflated Sharpe: N = 12** strategii-kandydatów na „portfel” (8 momentum 4P + równy podział + V1–V3).
  Lokata i złoto to punkty odniesienia, nie kandydaci. Wrażliwość: pokażę też N = 14.

## 5. Ocena (tylko część rozwojowa, przed otwarciem danych odłożonych)

Dla każdego wariantu i porównania:
- zwrot roczny na rękę, **maks. obsunięcie**, najdłużej pod kreską, liczba transakcji, koszty, podatek (jak 4P);
- **Sharpe** z miesięcznych zwrotów wartości konta w PLN ponad lokatę, w skali roku;
- **Sharpe po cięciu 2×, 3×, 4×** (ZASADY cz. 4: mediana na żywo −73%) — to jest liczba „czego się realnie spodziewać”;
- **Deflated Sharpe** (Bailey & López de Prado: N = 12, wariancja Sharpe między próbami, skośność, kurtoza) —
  próg ≥ 0,95; **t = Sharpe × √lat**, próg t > 3 (uczciwie: przy 8 latach to Sharpe > 1,06 — prawie na pewno nikt nie
  przejdzie; to informacja, nie porażka procesu);
- **PBO** (CSCV) na macierzy miesięcznych zwrotów 12 kandydatów, 8 bloków po 12 mies. (70 kombinacji), próg < 0,5.
  Przy 12 strategiach PBO jest zgrubne — opiszę to w raporcie;
- **walk-forward:** reguły nie mają parametrów dopasowywanych do danych (wszystko ustalone z góry, σ i trend tylko
  z przeszłości, prognozy OVX z walk-forward 3A), więc walk-forward = **wyniki w 4 kolejnych oknach 2-letnich**
  (2016–18, 18–20, 20–22, 22–24) — czy przewaga (jeśli jest) nie stoi na jednym okresie;
- najgorszy miesiąc i najgorszy rok; obsunięcie w 2018 (krypto), 2020-03, 2022.

**Reguła wyboru zwycięzcy (ustalona teraz, D7):** spośród V1–V3 wygrywa **najprostszy** wariant, chyba że bardziej
złożony ma na części rozwojowej jednocześnie wyższy Sharpe i nie gorsze maks. obsunięcie (kolejność prostoty:
V1 < V2 < V3). Porównanie wariantów — przy kosztach bazowych. Następnie zwycięzca musi mieć wyższy Sharpe niż
równy podział (B1) **w obu wersjach kosztów (×1 i ×2)**; jeśli nie → konto „system” wykonuje **równy podział**
(też reguła, też automatycznie). Wybór robi skrypt, nie ja.

**Wynik backtestu nie uprawnia do prawdziwych pieniędzy (D11).** Próg t > 3 jest nieosiągalny przy tej długości danych.
Decyzję o prawdziwych pieniądzach użytkownik podejmuje dopiero na podstawie wyniku konta „system” na żywo; warunki
ustalimy osobno.

Raport: `reports/etap5-rozwoj-{data}.md` → pokazuję i czekam.

## 6. Dane odłożone — otwierane raz

- Mechanizm w kodzie: stała `HOLDOUT_START = 2024-10-06`. Każdy backtest z końcem > HOLDOUT_START odmawia, chyba że
  wywołany przez `open_holdout()`.
- **Przed pierwszym przeliczeniem** (nawet części rozwojowej) zapis do `runs` (stage `5-prereg`): hash pełnych definicji
  V1–V3 + reguła wyboru. Test w bramce: hash definicji w kodzie = hash z prerejestracji (zmiana reguł → bramka czerwona).
- `open_holdout()` działa tylko, gdy w `runs` nie ma wiersza `5-holdout`; zapisuje go (data, hash) i liczy wszystkie
  7 przebiegów na 2024-10-06 … 2026-10-05. Drugie wywołanie odmawia. Raport `reports/etap5-odlozone-{data}.md`.
- Po otwarciu: **żadnych zmian reguł.** Jeśli wynik będzie zły — zapisuję to i nie poprawiam pod ten okres. Nowy
  wariant później = nowa próba, ocena tylko na przyszłych danych (konto „system”/nowe konto), nigdy na tym okresie.
- **Uczciwie (D8): te 2 lata nie są dziewicze.** Backtest 4P (równy podział vs momentum) i wybór mistrzów 3A (w tym
  OVX dla WTI) już objęły ten okres, a ZASADY wspominają stratę trendu 2024–25. Nowe warianty V1–V3 nie były na nim
  liczone, ale wiedza o nim istnieje. Jedynym naprawdę czystym testem jest konto „system” od dnia startu.

## 7. Konto „system” w grze na sucho

- Nowe konto w data/paper.duckdb: `name = "system"`, 1000 zł, start = pierwszy dzień decyzji po otwarciu danych
  odłożonych. Kolumna `momentum_variant` = momentum_1m (jak gra 1); nowa kolumna/tabela z id zwycięskiego wariantu
  i hashem definicji (migracja schematu paper.duckdb).
- **Wykonuje się samo:** krok `src/paper_system.py run` dopisany na końcu tools/snapshot_daily.sh (po build_features);
  w dni inne niż dzień decyzji nic nie robi. W dniu decyzji liczy wagi z R1–R5 i składa zlecenia przez `paper.place`
  z powodem „reguła etapu 5: {wariant} {hash}” i migawką (σ, e_i, wagi, źródło σ ropy). Ten sam kod liczy backtest
  i konto — test zgodności: zlecenia konta = transakcje backtestu dla tych samych dni.
- **Ręcznie nie da się nim handlować** (CLI odmawia buy/sell na koncie „system”; anulowanie tylko z powodem w dzienniku).
- **Warunek wyłączenia ustalony z góry (ZASADY 5.6, D9):** obsunięcie konta > 1,5 × najgorsze obsunięcie zwycięzcy
  z części rozwojowej → konto przestaje składać zlecenia, przechodzi w gotówkę i raport to zgłasza. Nie zmienia reguł.
- **Raport porównawczy** (`uv run src/paper.py compare`): gra 1 vs system vs równy podział vs lokata od wspólnej daty
  startu — wartość, obsunięcie, liczba transakcji, koszty, podatek, a dla gry 1 odsetek decyzji zgodnych z systemem.
  Na górze stała uwaga: przy Sharpe ~1 odróżnienie umiejętności od szczęścia wymaga ~2–3 lat; przez pierwsze miesiące
  oceniamy proces (dyscyplinę, zgodność z regułą), nie wynik.

## 8. Testy (do bramki)

- PIT: perturbacja cen po D 22:00 nie zmienia wag ani zleceń z dnia D (jak tests/test_pit_next_day.py); prognoza OVX
  brana z datą ≤ D.
- Sufit krypto zawsze ≤ 25% po rebalansie; wagi sumują się do 1 − część na lokacie.
- R5: brak transakcji, gdy nic nie przekracza progów; wyjście z trendu wykonuje się od razu.
- R4: przy mistrzu = fallback źródło σ = R1 (z wpisem w migawce).
- Dane odłożone: backtest z końcem > 2024-10-05 bez `open_holdout` → błąd; drugie otwarcie → błąd; hash definicji =
  prerejestracja.
- Konto „system”: odmowa ręcznych zleceń; zgodność zleceń z backtestem; warunek wyłączenia.
- Każdy test ochronny sprawdzony mutacją („zepsuj, odtwórz, zweryfikuj”).

## 9. Kolejność pracy (każdy krok kończy bramka + commit)

1. Akceptacja planu → wpisy D1–D9 do docs/DECISIONS.md.
2. Wsteczne dopisanie prób 4P do `runs`; moduł `src/ms/rules.py` (R1–R5) + testy; prerejestracja hasha w `runs`.
3. `src/backtest_rules.py` → część rozwojowa → raport → **pokazuję i czekam** (zwycięzcę wskazuje reguła D7).
4. `open_holdout()` — jeden raz, raport → pokazuję.
5. Konto „system” + krok w snapshot_daily.sh + `paper.py compare` + testy; STAN i DECISIONS zaktualizowane.

## 10. Decyzje (zaakceptowane 2026-10-07; D5 zmienione przez użytkownika, D11 dopisane)

| | pytanie | decyzja |
|---|---|---|
| D1 | Aktywa portfela | BTC, ETH, XAG, WTI jak w 4P; XAU tylko porównanie. (ZASADY wskazują Brent zamiast WTI jako instrument — zmiana aktywa = osobny etap, nie tu.) |
| D2 | σ „z 60–250 dni” | średnia σ_60 i σ_250 (szybka reakcja + stabilność); alternatywa: max(σ_60, σ_250) — ostrożniej |
| D3 | Nadwyżka ponad sufit krypto | na XAG i WTI proporcjonalnie (gotówka tylko z filtra trendu) |
| D4 | Filtr trendu | ekspozycja stopniowana (odsetek dodatnich okien 3/6/9/12 mies.), nie 0/1 — mniej szarpania przy granicy |
| D5 | σ ropy w V3 | OVX/100 × k (mediana z 3 lat ilorazu zrealizowana 21d / OVX, tylko przeszłość) — pkt R4; bez przeliczania p na σ; brak OVX/k albo mistrz nie na OVX → σ z R1 |
| D6 | Rebalans | sprawdzany raz w miesiącu (dzień decyzji), nie codziennie; ±25% względnie; próg zlecenia 1% kapitału |
| D7 | Wybór zwycięzcy | najprostszy, chyba że złożony lepszy w Sharpe i nie gorszy w obsunięciu; zwycięzca musi pobić równy podział w Sharpe przy kosztach ×1 **i** ×2, inaczej system = równy podział |
| D8 | Dane odłożone częściowo widziane (4P, 3A) | akceptujemy z jawną adnotacją w raporcie; czysty test = konto „system” |
| D9 | Wyłączenie konta „system” | obsunięcie > 1,5 × najgorsze z części rozwojowej → gotówka + zgłoszenie |
| D10 | Krypto dopiero od 2018-08 | zostaje okno 10 lat jak w 4P (porównywalność), a raport pokazuje osobno podokres 2018-09 … 2024-10 z kompletem 4 aktywów. Nie podmieniam źródła cen krypto na dłuższe (Coin Metrics) — to zmieniłoby podstawę 4P |
| D11 | Prawdziwe pieniądze | wynik backtestu etapu 5 NIE uprawnia do prawdziwych pieniędzy (t > 3 nieosiągalne przy tej długości danych); decyzja wyłącznie na podstawie konta „system” na żywo, warunki ustalane osobno |
| — | Koszty ×2 | każdy przebieg także przy kosztach ×2 (test wrażliwości, nie zwiększa N); zwycięzca musi pobić równy podział w obu wersjach |
