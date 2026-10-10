# Etap 4N — walidacja klasyfikatora Qwen (E1–E4): plan wykonania

Stan: 2026-10-07. Podstawa: docs/ETAP4N-PLAN.md pkt 5–6 (zbiory i progi ustalone 2026-10-06, PRZED pierwszym
uruchomieniem modelu). Ten dokument nie zmienia progów — dopisuje liczebności, szczegóły wykonania i stan złota.
Wszystko lokalnie: Ollama na 127.0.0.1 przez `ms.llm` (zasada „tylko lokalnie”). Qwen nie był dotąd uruchamiany na niczym.

## 1. Modele i prompt (próby w `runs`)

| model | digest | rozmiar |
|---|---|---|
| `qwen2.5-coder:32b` | b92d6a0bd47e | 32,8B, Q4_K_M |
| `qwen3:30b-a3b-instruct-2507-q4_K_M` | 19e422b02313 | 30,5B MoE, Q4_K_M |

- **Jeden prompt (`v1`)** — wspólny szablon; definicje kodów z ref/taxonomy.csv (kolumna `prompt`, od 2026-10-07 z konwencjami
  wzorca E2 — prompt produkcyjny = prompt walidowany); lista dozwolonych kodów zależy od zadania (E1: 12 kodów BBDS; E2: kody
  taksonomii; E3: 3 klasy). Odpowiedź JSON wymuszona schematem (`format` w Ollama): `cause`, `cause_secondary`,
  `confidence` (low/med/high), `evidence_ids`. Temperatura 0, seed 20261007, kontekst 32k. Bez cen na wejściu.
- Przykłady (few-shot): E1 — z BBDS **wyłącznie 1900–1949** (1 na kod, wybór deterministyczny: najwcześniejszy dzień
  z cytatem); rozszerzenia — po 2 przykłady napisane ręcznie, zapisane w `ref/prompt_examples.csv` **przed** pierwszym
  uruchomieniem. Hash szablonu + przykładów = `prompt_hash`.
- W walidacji **1 przebieg** na pozycję (temp. 0, stały seed → 3 przebiegi dałyby to samo); 3 przebiegi i zgodność
  przebiegów dotyczą produkcji (pkt 5 planu 4N).
- **Próby w `runs`: 2** (stage `4N-val`) — po jednej na (model, prompt v1), każda obejmuje E1–E4. **Limit etapu: 3 próby**
  → po porażce zostaje jedna zmiana promptu na lepszy z modeli; potem raport „nie da się wiarygodnie”.

## 2. Zbiory testowe, miary, progi

| zbiór | złoto | n | wejście | miara | próg (z planu 4N) |
|---|---|---|---|---|---|
| **E1** BBDS | kategoria główna kodera | **492** jednostki (dzień, koder, cytat) z lat 1950–2022, kod z 12 (bez „other”), z cytatem | cytat (`passage`) | dokładność, κ Cohena, macierz pomyłek, bootstrap 95% (blokowy po dniach) | **κ ≥ 0,695** = max(0,60; κ_ludzie − 0,10), κ_ludzie = **0,795** [0,771; 0,819] (1 298 par koderów, 1950–2022) — wpis w DECISIONS przed uruchomieniem |
| **E2** komentarze WGC (zmiana 2026-10-07) | zdanie WGC o przyczynie ruchu + kod przypisany wg ref/e2_wgc_rules.md (asystent, nie Qwen; ref/e2_wgc_gold.csv); kontrola użytkownika: 20 losowych (ref/e2_wgc_check20.xlsx) | 37 miesięcy (2021-03…2026-08; 17 wyłączonych z powodem; 25 zależnych od konwencji z definicji kodów) | cytat (+ wariant zamaskowany) | dokładność, κ | dokładność ≥ 0,75 **i** κ ≥ 0,60, oba warianty |
| **E3** epizody Hamilton / Baumeister–Kilian (**kontrola, nie bramka** — decyzja 2026-10-07) | dominująca przyczyna wg literatury (ref/oil_episodes.csv); sporne 1979 i 1986 poza metryką, pokazane osobno | 7 liczonych + 2 sporne (chronologia do 2003) | wszystkie wpisy chronologii z okna epizodu, bez nazwy i dat (+ wariant zamaskowany) | trafienia | ≥ 14 z 20 |
| **E4** wejście produkcyjne | dni z etykietą kalendarza: FOMC 26, OPEC 12, hack 2, ETF 2 = **42 dni** (2015–2026) | slugi URL-i GDELT z okna [D−1 22:00, D 22:00] UTC, bez par USA–USA (mediana 784 adresy/dzień) + opis z kodów CAMEO | zgodność z kalendarzem (trafienie = kod dnia z kalendarza) | ≥ 0,60 |

Kontrola pamięci (E2, E3): wariant z krajami i organizacjami zamienionymi na znaczniki, bez lat. Spadek > 0,15 =
sygnał zgadywania z pamięci; do produkcji tylko gdy wariant zamaskowany też przechodzi próg.

**Reguła wejścia (zmieniona 2026-10-07 przed E3):** `validated = true` dla (model, prompt) tylko gdy E1, E2 (+ wariant
zamaskowany) i E4 przeszły; E3 raportowane jako kontrola. Do tego czasu klasyfikator **nie trafia do statusu ani dashboardu** (test w bramce). Wybór modelu: wg E1 i E2.

## 3. Stan złota — uczciwie

- **E1, E4: gotowe** (dane w bazie).
- **E2: wzorzec z komentarzy WGC** (2026-10-07; etykiety użytkownika wycofane; arkusz poza kopią publiczną). Zamrożony przed przebiegiem.
- **E3: złoto do przygotowania** — `ref/oil_episodes.csv` (epizody i dominująca przyczyna) przepisane z Hamilton (2011)
  „Historical Oil Shocks” i Baumeister–Kilian (2016) „Forty Years of Oil Price Fluctuations” z cytatem/stroną dla
  każdego epizodu; plik w commicie **przed** uruchomieniem E3. Do Twojego wglądu w raporcie.
- **E4: spodziewana słabość** — nasza baza GDELT jest filtrowana do zdarzeń konfliktowych z USA wśród aktorów
  (decyzja etapu 1), więc w dniach FOMC/OPEC slugi rzadko mówią o polityce pieniężnej czy OPEC. Plan 4N przewiduje ten
  przypadek („klasyfikator umie czytać, ale nie ma czego”) — wynik raportujemy bez zmiany progu.

## 4. Kolejność wykonania

1. κ_ludzie → DECISIONS (zamraża próg E1). `ms.llm`: schemat JSON i opcje (temp., seed, kontekst) — tylko 127.0.0.1.
2. Prompt v1 + `ref/prompt_examples.csv` → commit (hash zamrożony), wpisy prób w `runs`.
3. E1 i E4 na obu modelach (w tle, `caffeinate`; wyniki per pozycja w tabeli `cause_validation`).
4. E3: złoto → commit → przebieg na obu modelach (+ wariant zamaskowany).
5. E2: po Twoich etykietach (`build_causes.py e2-check`) → przebieg (+ zamaskowany) → werdykt.
6. Raport `reports/move-causes-validation-<data>.md`: miary, przedziały, macierze pomyłek, kontrola pamięci, werdykt
   per model. `validated` w `move_causes` zmienia się wyłącznie po przejściu wszystkich progów.

## 5. Trzecia próba — NIEZUŻYTA (decyzja 2026-10-08)

Wynik prób 1–2 (qwen3:30b-a3b, qwen2.5-coder:32b, prompt v1 98dc8d39f7050718): **validated = false** dla obu
(E1 κ ≈ 0,60 < 0,695; E4 0 trafień). Trzecia, ostatnia próba etapu nie jest zużywana teraz. Ustalone z góry na nią:

1. **E1 — definicje kodów:** porażka częściowo przez doprecyzowanie `monetary` z 2026-10-07 (stopy, oczekiwania co do
   stóp, rentowności). Definicje mają rozdzielać:
   - **dane i perspektywy gospodarki → `macro`, nawet gdy w ich następstwie ruszają stopy / rentowności;**
   - **decyzje i komunikaty banku centralnego → `monetary`.**
   (Macierz pomyłek prób 1–2: ~50 ze 160 jednostek `macro` sklasyfikowanych jako `monetary`.) Zmiana definicji =
   zmiana promptu = trzecia próba; wzorzec E2 trzeba wtedy sprawdzić pod nowe definicje (wiersze „rentowności → monetary”).
2. **E4 — nowy test:** obecne E4 to wada testu, nie miara modelu (wejście GDELT filtrowane do zdarzeń konfliktowych nie
   daje szansy na odpowiedź w dniach FOMC/OPEC). Nowe E4 na wiadomościach RSS z `data/news.duckdb`, gdy będzie
   **≥ 8 tygodni danych** (zbieranie od 2026-10-07 → najwcześniej 2026-12-02). **Plan nowego E4 (dni i ich wzorzec,
   wejście, okno czasowe, próg) — spisany i zaakceptowany PRZED zebraniem tych danych**, żeby nie dopasować testu do wyniku.

### 5a. Trzecia próba — wykonanie (2026-10-08)

Model qwen3:30b-a3b (szybszy przy równej trafności), prompt v2 (definicje macro/monetary z pkt 5.1), wzorzec E2 po
przeglądzie (1 wiersz zmieniony) i trzeciej niezależnej kontroli (NIE = 0), **bramka: E1, E2 (+ zamaskowany), E4-hist**
(D5; E4 na RSS = kontrola w produkcji), E3 kontrola. Ostatnia próba etapu — po niej koniec niezależnie od wyniku.
