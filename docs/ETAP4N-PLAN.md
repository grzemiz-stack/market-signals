# Etap 4N-etykiety: przyczyny dużych ruchów cen — PLAN (bez kodu)

Stan: 2026-10-06. Podstawa: docs/ZRODLA-PRZYCZYN.md (Priorytet 1, pipeline „Jak z tego zrobić etykiety”).
Status: **plan do akceptacji — nic nie pobrane do bazy, nic nie napisane.**

## 0. Cel i granica (zasada PIT — nienegocjowalna)

Tabela `move_causes` odpowiada na pytanie „dlaczego aktywo X ruszyło się mocno w dniu D”. Służy **wyłącznie** do:
1. wyjaśniania dużych ruchów w statusie / raportach,
2. badań zdarzeń (4H) — jako lista dni z przyczyną, porównywana z cenami.

**Nigdy jako cecha prognozy.** Etykieta przyczyny to wiedza po fakcie (powstaje po zamknięciu dnia D, często z tekstów
pisanych później). Pilnowanie w kodzie, nie w pamięci:
- test w bramce: żaden moduł z `features`, `labels`, `baselines`, `gbm`, `prob`, `decompose`, `registry`, `models/`,
  `analogs`, `trading`, `paper` nie odwołuje się do `move_causes` (grep po źródłach + test, że `build_features` daje
  identyczny wynik z tabelą pustą i pełną);
- kolumna `known_at` = chwila utworzenia etykiety (nie dzień ruchu) — gdyby ktoś jednak sięgnął przez `as_of`,
  dostanie tylko etykiety już istniejące w danej chwili, czyli dla historii: nic.
- Zasada LLM bez zmian: Qwen tylko **klasyfikuje tekst** do taksonomii. Nie ocenia „co na co wpływa” i nie dostaje cen.

## 1. Źródła Priorytetu 1 — sprawdzone dziś (dostęp, licencja, format)

Pobrane próbnie do scratchpadu (nie do repo, nie do bazy). Wynik:

| # | Źródło | Dostęp | Format i zawartość (sprawdzone w pliku) | Licencja | Uwagi / ryzyka |
|---|---|---|---|---|---|
| P1 | BBDS „What Triggers Stock Market Jumps” | ✅ eksport xlsx z Google Sheet (1,8 MB) | 8 zakładek: `wsj_codings` **3 501** kodowań, **1 179** dni skoku (|ruch| > 2,5%) **1900-01-03…2022-11-30**, kategoria główna + poboczna, łatwość kodowania, pewność dziennikarza; `key_passages` 3 501 cytatów z gazet; `jumps by day` z udziałem kategorii; `all_codings` (10 650) **pusta** w arkuszu | brak podanej licencji (materiał akademicki) | To skoki **akcji USA**, nie surowców — w dokumencie „6–8 tys.” to wersja wielokrajowa, arkusz ma tylko USA/WSJ. Użycie: taksonomia, few-shoty i **zbiór złoty do walidacji Qwena** (ludzkie kodowania, kilku koderów na dzień). Licencja: tylko użytek prywatny/badawczy, `license='academic-unspecified'`. |
| P2 | AI-GPR + Oil GPR (Caldara–Iacoviello) | ✅ CSV bezpośrednio (`ai_gpr_files/…`) | dzienny: 24 380 wierszy **1960-01-01…2026-09-30**; kolumny GPR_AI, GPR_OIL, THREATS/ACTS, GPR_OIL_THREATS/ACTS, Oil GPR wg regionów; miesięczne: typ zdarzenia, kraj, pary krajów | AI-GPR: **niepodana** (klasyczny GPR CC BY) | Wartości liczone modelem językowym i przeliczane wstecz → tylko `latest_vintage` (jak STEO), bez wersji PIT — dla etykiet po fakcie to wystarcza. Licencja do potwierdzenia mailem do autorów przed jakimkolwiek udostępnieniem. |
| P3a | SF Fed Bauer–Swanson | ✅ xlsx (300 kB) | 361 komunikatów **1988-02-04…2023-12-13** (FF1, FF2, ED1–4, SP500, TNOTE…, flaga „Unscheduled”); miesięczne MPS | publiczne (Fed) | **Kończy się na 2023-12** — nie 2026 jak w dokumencie. |
| P3b | Jarociński–Karadi (GitHub) | ✅ CSV (raw.githubusercontent) | `shocks_fed_jk_t.csv`: **1990-02-08…2024-01-31**, MP (szok stopy) vs CBI (szok informacyjny), wersje „pm” i „median” | repo **bez pliku licencji**; dane z licencjonowanych tick-data, autorzy publikują do cytowania | Po 2024-01 brak niespodzianek — FOMC 2024–2026 dostaje etykietę `kalendarz:fomc` bez wielkości (flaga `no_surprise_measure`). |
| P4 | EIA „World Oil Market and Oil Price Chronologies 1970–2003” | ✅ kopia laohamutuk.org (HTML, latin-1); ✅ oryginał EIA w Wayback (`eia.gov/emeu/cabs/chron.html`, zrzut 2025-02-06) | ~**567 wpisów miesięcznych** w 68 blokach rocznych + krótka lista nagłówkowa; **dokładność: miesiąc**, dzień tylko czasem w tekście | domena publiczna (rząd USA) | Źródłem prawdy będzie **oryginał EIA z Wayback**, kopia tylko do kontroli zgodności. Zwykłe pobranie zarchiwizowanej strony — nie obchodzi żadnej blokady. |
| P5 | Wikipedia „Chronology of world oil market events” | ✅ wikitext przez `action=raw` | **294 wpisy** z datą dzienną, sekcje roczne 1934…**1997** (nie ~2005 jak w dokumencie), przypisy do źródeł | CC BY-SA 4.0 | Share-alike: przy udostępnianiu pochodnych trzeba tej samej licencji — prywatnie bez znaczenia; zapisać `license='CC BY-SA 4.0'`. Zapisać `oldid` wersji strony. |
| P6 | Nazer–Pescatori, IMF WP/22/183 | ❌ **403 Access Denied** (Akamai) na imf.org i elibrary | PDF z tabelą 101 spotkań OPEC | darmowy PDF | Nie obchodzimy blokady → **skrzynka ręczna `data/inbox/imf/`**: użytkownik pobiera PDF w przeglądarce, parser tabeli po pierwszym pliku. Do tego czasu OPEC = Känzig (169 dat, już w bazie) bez typu decyzji. |
| P7 | DefiLlama hacks API | ✅ JSON (350 kB) | **1 293** hacki **2011-06-19…2026-10-01**: data (dzień), nazwa, klasyfikacja, technika, kwota USD, łańcuchy, bridgeHack, zwrócone środki; **43** z kwotą ≥ 100 mln USD | API darmowe; warunków nie udało się otworzyć (403 na stronie docs) | `license='defillama-terms-unverified'`; do potwierdzenia przed udostępnieniem. Kwota w USD z chwili zgłoszenia (nie przeliczać). |
| P8 | Daty stałe (halvingi, depegi, ETF, FTX, zakazy w Chinach) | — | ręcznie: plik `ref/crypto_events.csv` w repo (fakty publiczne) | fakty | Każdy wiersz **z URL-em źródła i dokładnością** (`day`/`month`). Kilka dat w dokumencie wymaga doprecyzowania do dnia: FTX (8.11.2022 ogłoszenie Binance / 11.11.2022 upadłość — dwa wiersze), zakazy 2017 (4.09 ICO, 15.09 giełdy) i 2021 (18–21.05, 24.09). Sprawdzam każdą datę u źródła przy wpisywaniu. |

Spoza Priorytetu 1, bo o to prosisz w walidacji: **Hamilton „Historical Oil Shocks”** i **Baumeister–Kilian „Forty
Years of Oil Price Fluctuations”** (W7) — przepisuję ręcznie ~20 epizodów do `ref/oil_episodes.csv`
(epizod, daty od–do, przyczyna według autorów: podaż / popyt globalny / popyt zapobiegawczy-zapasy, cytat, strona).
PDF-y otwieram przy przepisywaniu; jeśli któryś jest za blokadą — skrzynka ręczna.

Każde źródło: surowy plik do `data/raw/` + wpis w `manifest.jsonl` (sha256, URL, data), jak dotąd.
**Ograniczenie dla krypto i metali:** żadne źródło P1–P8 nie daje „przyczyny” dla złota/srebra (to W1/W2 — Priorytet 2).

## 2. Tabela `move_causes`

Jeden wiersz = jedna przypisana przyczyna dużego ruchu. Dzień może mieć kilka wierszy (kilka źródeł, przyczyna główna
i poboczna). Tylko dopisywanie; nowa wersja modelu lub promptu = nowe wiersze, stare zostają.

| kolumna | typ | znaczenie |
|---|---|---|
| `asset` | VARCHAR | XAU, XAG, WTI, BRENT, BTC, ETH |
| `day` | DATE | dzień zamknięcia z ruchem (dzień 0 w sensie 4H) |
| `ret` | DOUBLE | log-zwrot zamknięcie/zamknięcie (te same szeregi co etykiety: stitch_metals, EIA spot, Binance) |
| `sigma` | DOUBLE | odchylenie std. log-zwrotów z **252 poprzednich** sesji (bez dnia D) |
| `z` | DOUBLE | ret / sigma |
| `cause` | VARCHAR | kod z taksonomii (pkt 3) |
| `rank` | TINYINT | 1 = główna, 2 = poboczna |
| `label_source` | VARCHAR | `calendar` / `study` / `llm` |
| `source_ref` | VARCHAR | identyfikator: np. `fomc:2008-01-22`, `eia_chron:1990-08`, `bbds:…`, `defillama:<id>`, hash wejścia LLM |
| `evidence` | VARCHAR | krótki tekst, na którym oparto etykietę (opis z kalendarza, cytat z chronologii, nagłówki/URL-e dla LLM) |
| `model` | VARCHAR | NULL dla calendar/study; dla LLM nazwa + **digest** z `ollama list` (np. `qwen2.5:32b@<digest>`) |
| `prompt_version` | VARCHAR | NULL / `v1`…; plus `prompt_hash` (sha256 pełnego promptu z few-shotami) |
| `confidence` | DOUBLE 0–1 | calendar: 1,0 przy dniu 0, 0,6 przy dniu +1; study: z pewności źródła (np. BBDS JournalistConfidence 3/2/1 → 1/0,67/0,33; chronologia miesięczna → 0,5); llm: zgodność 3 przebiegów × pewność zadeklarowana (pkt 5) |
| `validated` | BOOLEAN | czy wersja modelu+promptu przeszła progi z pkt 6 (bez tego — nie pokazujemy w statusie) |
| `license` | VARCHAR | licencja źródła etykiety (NC/SA/academic — do wycięcia przy ewentualnej sprzedaży) |
| `run_id` | VARCHAR | wpis w `runs` (definicje + hash, jak w 4H) |
| `known_at` | TIMESTAMP | chwila utworzenia etykiety (pkt 0) |

Klucz unikalny: (`asset`, `day`, `cause`, `label_source`, `source_ref`, `model`, `prompt_hash`). Ponowny przebieg
bez zmian = 0 nowych wierszy (idempotencja, test w bramce).

Pomocnicze tabele (surowe dane źródeł, nie etykiety): `cause_events` (wpisy z P4, P5, P7, P8, epizody W7: data,
dokładność, tekst, źródło, licencja) oraz kolumny `surprise_*` dla FOMC dołączone do istniejącego `events_calendar`
(SF/JK) i `decision` dla OPEC (P6, gdy przyjdzie PDF).

## 3. Taksonomia (BBDS + rozszerzenia z dokumentu)

Kody BBDS (z arkusza, 17 kategorii) zwinięte do 12, plus 7 rozszerzeń dla naszych aktywów:

| kod | BBDS | | kod (rozszerzenie) | znaczenie |
|---|---|---|---|---|
| `macro` | macroeconomic news & outlook | | `oil_supply` | podaż ropy: OPEC, awarie, wojny w krajach producentach, sankcje na eksport |
| `monetary` | monetary policy & central banking | | `global_demand` | popyt globalny (recesja, Chiny, PMI) — dla surowców |
| `sovmil` | sovereign military & security actions | | `metal_shortage` | fizyczny niedobór metalu (dostawy, premie, LBMA/COMEX) |
| `terror` | terrorist attacks / non-state violence | | `crypto_regulation` | regulacje, zakazy, pozwy SEC |
| `commodities` | commodities | | `crypto_hack` | hack / kradzież / upadek protokołu |
| `trade_policy` | international trade policy | | `crypto_etf` | ETF: decyzje, start notowań, duże przepływy |
| `regulation` | regulation | | `leverage_liquidations` | dźwignia, kaskady likwidacji, depegi stablecoinów |
| `fiscal` | government spending + taxes | | | |
| `elections` | elections & political transitions | | | |
| `fx_capital` | exchange rate policy & capital controls | | | |
| `corporate_foreign` | corporate earnings + foreign stock market | | | |
| `unknown` | unknown & no explanation / no article | | | |

„other – specify” z BBDS: w walidacji E1 wyłączone (niejednoznaczne), liczba podana w raporcie.
Mapa BBDS → kody: plik `ref/taxonomy.csv` (w repo), zatwierdzony przed pierwszym przebiegiem.

## 4. Pipeline (kolejność z dokumentu)

**Krok 1 — duże ruchy.** Dni z |z| > 2,5 dla każdego aktywa (σ z 252 poprzednich sesji, tylko przeszłość). Okresy:
XAU/XAG od początku stitch_metals, WTI od 1986-01-02, BRENT od 1987-05-20 (dzienne EIA), BTC/ETH od Binance.
**Uwaga:** ropa 1970–1985 nie ma cen dziennych w bazie — chronologia z tych lat służy tylko do walidacji tekstu (E2),
nie do dopasowań dzień–ruch.

**Krok 2 — kalendarz (deterministycznie, bez LLM).** Dla każdego zdarzenia: T (known_at) → dzień 0 = pierwsze
zamknięcie znane po T (ta sama funkcja co w `ms.hyp_events.car_table`). Dzień ruchu = dzień 0 → `confidence 1,0`;
dzień +1 → 0,6. Reguły aktywo ← zdarzenie:
- FOMC (+ wielkość niespodzianki SF/JK do 2023/2024) → wszystkie aktywa, `monetary`;
- OPEC (Känzig; typ decyzji z P6 gdy będzie) → WTI, BRENT, `oil_supply`;
- WPSR (dzień publikacji) → WTI, BRENT, `oil_supply` tylko gdy |niespodzianka zapasów| w górnych 10% (definicja z 2b w STAN, tylko przeszłość); inaczej nie etykietuje — publikacja jest co tydzień, sama data nic nie wyjaśnia;
- huragan GOM → WTI, BRENT, `oil_supply`;
- ETF (decyzja SEC, start notowań) → BTC/ETH `crypto_etf`; halving → BTC, kod do ustalenia (**decyzja D4**);
- depeg, FTX, upadki → BTC, ETH `leverage_liquidations`; zakazy w Chinach → `crypto_regulation`;
- hack ≥ 100 mln USD (P7) → BTC, ETH `crypto_hack`;
- skok Oil GPR ACTS (górne 5% vs mediana 90 dni, declustering 20 dni — jak w 4H) → WTI, BRENT `oil_supply`/`sovmil`; skok GPR_AI ACTS → XAU, XAG `sovmil`.
Kilka trafień jednego dnia → kilka wierszy; `rank` 1 dla zdarzenia o najwyższym priorytecie (kolejność listy wyżej).

**Krok 2b — badania (study).** Wpisy z datą dzienną z P5 (Wikipedia, do 1997) i dni wewnątrz epizodów W7 → etykieta
`study` dla WTI/BRENT, `confidence` 0,5–1,0 wg dokładności daty. Chronologia EIA (P4) ma dokładność miesięczną → tylko
`confidence 0,5` i tylko gdy w danym miesiącu jest dokładnie jeden duży ruch.

**Krok 3 — Qwen dla reszty dni.** Wejście: teksty z okna [D−1 22:00 UTC, D 22:00 UTC]. **Tu jest najsłabsze ogniwo:**
- GDELT w naszej bazie zaczyna się **2015-02-18** i **nie ma nagłówków** — ma tylko `source_url`, kody CAMEO, aktorów,
  ton. Wejściem dla Qwena byłyby slugi z URL-i (często czytelne: `/opec-agrees-output-cut-…`) + opis zdarzenia z kodów.
  Słabsze niż nagłówki; zmierzymy to osobno (E3).
- Przed 2015 nie mamy żadnego strumienia tekstów. N5 (57 mln nagłówków 1990–2025, licencja NC) to rozwiązuje, ale jest
  duże i NC → **decyzja D2**.
- Few-shoty: z `key_passages` BBDS (tylko dni z lat **1900–1949**, żeby nie przeciekały do zbioru testowego E1)
  + po 2 przykłady na każde rozszerzenie, napisane ręcznie i zapisane w repo.
- Odpowiedź w JSON (schemat wymuszony przez `format` w Ollama): `cause`, `cause_secondary`, `confidence` (low/med/high),
  `evidence_ids`. Temperatura 0, stały seed, 3 przebiegi; zgodność przebiegów wchodzi do `confidence`.
- Bez cen na wejściu — Qwen nie wie, w którą stronę i jak mocno poszło aktywo (inaczej dopasuje narrację do ruchu).

**Model.** `ollama list` pokazuje tylko **qwen2.5-coder: 7b / 14b / 32b** (32b: Q4_K_M, kontekst 32k, 19 GB; Mac ma 48 GB RAM).
To warianty do kodu, nie ogólne instrukcyjne — do klasyfikacji tekstów lepszy byłby `qwen2.5:32b-instruct` lub `qwen3:32b`
(pobranie ~20 GB, lokalnie, Apache 2.0, zero płatnych API) → **decyzja D1**. Walidacja (pkt 6) i tak rozstrzyga, który
model wchodzi; testujemy 2 modele (D1) × 1 prompt, żeby nie dopasowywać się do zbioru testowego (każda kombinacja
= próba w `runs`).

## 5. Pewność etykiet LLM

`confidence = (liczba przebiegów zgodnych z głównym / 3) × w`, gdzie w = 1 / 0,67 / 0,33 dla high/med/low.
Do statusu trafiają tylko etykiety z `validated = true` i `confidence ≥ 0,5`; reszta zostaje w tabeli jako `unknown`-kandydat.
To reguła z góry — nie kalibrujemy jej na wynikach walidacji.

## 6. Walidacja Qwena — zbiory i progi USTALONE PRZED pierwszym uruchomieniem

Trzy zbiory, każdy mierzy co innego. Wynik każdego w `runs` (model+digest, prompt_hash, n, miary, przedział ufności).

**E1 — BBDS `key_passages` (ludzkie kodowania, główny test ilościowy).** Zadanie: cytat z gazety → kategoria.
Test: dni z lat **1950–2022** (few-shoty tylko 1900–1949). Złoto: kategoria główna kodera; dni z kilkoma koderami
pozwalają policzyć **zgodność człowiek–człowiek** (κ Cohena) — liczę ją z arkusza przed uruchomieniem Qwena i wpisuję do
DECISIONS.md. **Próg:** κ(Qwen, człowiek) ≥ **max(0,60; κ_ludzie − 0,10)** na 12 kodach BBDS (bez „other”).
Raport: dokładność, κ, macierz pomyłek, przedział bootstrap 95%.

**E2 — chronologia EIA 1970–2003 (P4) + Wikipedia (P5, do 1997): ropa, tekst → przyczyna.** Zadanie: opis wpisu →
kod (głównie `oil_supply` / `global_demand` / `sovmil` / `monetary` / `macro`). Złoto musi pochodzić od człowieka, nie od
modelu: **150 wpisów** losowanych warstwowo po dekadach, etykietowanych przez Ciebie w arkuszu, który przygotuję (kolumny:
tekst, kod, „niejasne”); ~1 h pracy → **decyzja D3**. **Próg:** dokładność ≥ **0,75** i κ ≥ **0,60** (wpisy „niejasne” wyłączone,
ich liczba w raporcie).

**E3 — epizody Hamiltona i Baumeister–Kilian (~20, ekspercka przyczyna).** Zadanie: Qwen dostaje wszystkie wpisy
chronologii (P4/P5) z okna epizodu, bez nazwy epizodu i bez dat, i wskazuje dominującą przyczynę: podaż / popyt globalny /
popyt zapobiegawczy-zapasy. **Próg:** ≥ **14 z 20** (70%). Przy n = 20 przedział Wilsona jest szeroki (±20 p.p.) — dlatego
E3 jest warunkiem koniecznym, ale nie dowodem; dowodem jest E1+E2.

**E4 — wejście produkcyjne (GDELT, slugi URL-i, 2015–2026).** Ten sam rodzaj tekstu, który Qwen dostanie w kroku 3.
Złoto: dni, które mają etykietę kalendarza (FOMC, OPEC, hack ≥ 100 mln, ETF) — Qwen ich nie widzi jako kalendarza,
tylko czyta URL-e z okna. **Próg:** zgodność z kalendarzem ≥ **0,60** (niższy, bo kalendarz zna tylko jedną z możliwych
przyczyn, a w dniu FOMC może dominować co innego). Jeśli E4 nie przejdzie — krok 3 na GDELT nie wchodzi do statusu, nawet
gdy E1–E3 przeszły (klasyfikator umie czytać, ale nie ma czego).

**Kontrola pamięci modelu.** Qwen zna historię (embargo 1973, Kuwejt 1990) i może odpowiadać z pamięci zamiast z tekstu.
W E2 i E3 drugi wariant wejścia: nazwy krajów i organizacji zamienione na znaczniki (`[KRAJ_A]`, `[ORGANIZACJA]`), bez lat.
Spadek dokładności > 0,15 między wariantami = sygnał, że model zgaduje z pamięci → zapis w raporcie, a do produkcji
idzie tylko wtedy, gdy wariant zamaskowany też przechodzi próg.

**Reguła wejścia:** `validated = true` dla kombinacji (model, prompt) tylko gdy E1, E2, E3 i E4 przeszły (+ kontrola
pamięci). Progi nie zmieniają się po zobaczeniu wyników; zmiana promptu po porażce = nowa próba w `runs`, a limit to
**3 próby** na cały etap — potem raport „nie da się wiarygodnie”, bez dalszego strojenia.

## 7. Kolejność prac (po akceptacji)

1. Źródła P1, P2, P3a/b, P4 (Wayback EIA), P5, P7 → `data/raw` + manifest + `cause_events` / `events_calendar`; P8 i
   W7 ręcznie z URL-ami; P6 → skrzynka. Testy parserów na zapisanych próbkach.
2. `taxonomy.csv` + mapa BBDS; κ człowiek–człowiek z BBDS → DECISIONS.md (zamraża próg E1).
3. `move_causes` + krok 1 (duże ruchy) + krok 2 i 2b (kalendarz, badania) — bez LLM. Raport pokrycia: ile dużych ruchów
   na aktywo ma przyczynę z kalendarza/badań, ile zostaje dla Qwena.
4. Arkusz E2 do Twojego etykietowania (D3) → czekam na plik.
5. Walidacja E1–E4 (model z D1). Raport `reports/move-causes-validation-<data>.md`.
6. Krok 3 tylko jeśli walidacja przeszła. Raport `reports/move-causes-<data>.md`.
7. Test PIT w bramce (pkt 0), testy idempotencji, STAN, commit.

Nie w tym etapie: launchd (etykiety liczymy na żądanie), Priorytet 2 i 3 poza ewentualnym N5 (D2), użycie etykiet w 4H.

## 8. Decyzje (zatwierdzone 2026-10-06)

- **D1. Modele:** porównujemy dwa: `qwen2.5-coder:32b` (już był) i jeden instrukcyjny podobnej wielkości z ollama.com/library:
  **`qwen3:30b-a3b-instruct-2507-q4_K_M`** (MoE, 19 GB, czysto instrukcyjny bez trybu „thinking”; miejsce na dysku
  sprawdzone przed pobraniem: 760 GB wolne). Wybór modelu według wyniku na E1 i E2; każdy model = osobna próba w `runs`
  (2 z limitu 3).
- **D2.** Bez N5 na razie. Przed 2015 tylko kalendarz i badania.
- **D3.** Użytkownik oznacza wpisy chronologii do E2. Plik `ref/e2_gold_to_label.csv` (150 wierszy w kolejności
  losowej, warstwowo po dekadach — każdy początkowy fragment, np. pierwsze 100, jest też poprawną próbą). Kolumny: data,
  tekst wpisu, pusta `przyczyna` (dozwolone kody w nagłówku), `niejasne`. Minimum 100 oznaczonych; progi E2 bez zmian.
  **Qwen nie jest uruchamiany na wpisach E2, dopóki plik nie wróci oznaczony** — żadne wyniki modelu nie są pokazywane wcześniej.
- **D4.** Halving = nowe rozszerzenie `crypto_supply` (8 rozszerzeń w taksonomii).
- **D5.** Licencje bez podanych warunków: `license` z dopiskiem „niepotwierdzona”; tylko użytek prywatny.
- **P6.** PDF IMF użytkownik wrzuci ręcznie do `data/inbox/imf/`.
- Kolejność startu: P1–P5, P7, P8 + kalendarz (pkt 7.1–7.3).

## 9. Kandydat ≠ przyczyna (decyzja 2026-10-06)

Etykiety z kalendarza (i każde inne dopasowanie po dacie) mają `status='kandydat'`, `validated=false`.
**Ostateczna przyczyna wymaga potwierdzenia tekstem**: zwalidowany Qwen (po przejściu E1–E4) albo człowiek ->
`status='potwierdzona'`. Status/raporty pokazują kandydatów wyłącznie jako „tego dnia było: …” (funkcja
`ms.causes.describe_day`), nigdy jako przyczynę. Kolumna `status` dodana migracją w `ms.db.SCHEMA`.

## 10. Następne źródło dla złota: W1 — komentarze WGC (Gold Market Commentary, od 2013)

Po walidacji Qwena (E1–E4) i kroku 3 — pierwsze źródło tekstowe dla metali (dziś metale mają tylko kandydatów z FOMC
i AI-GPR). Zakres do rozpoznania przed pobraniem (jak w pkt 1): dostęp (strona/PDF, czy bez logowania), warunki WGC
(T&C — prawdopodobnie tylko użytek prywatny -> `license` z „niepotwierdzona” do czasu sprawdzenia), format i liczba
miesięcy (~150). Użycie: (a) potwierdzanie kandydatów dla XAU (miesięczny tekst „dlaczego złoto się ruszyło” ->
przyczyna dużych ruchów w tym miesiącu, z dokładnością do miesiąca), (b) zbiór walidacyjny złota 2013–2026
(pkt 4 w docs/ZRODLA-PRZYCZYN.md). Bez obchodzenia blokad: gdy wymagana rejestracja -> skrzynka `data/inbox/wgc/`
(już istnieje). Osobny plan po zamknięciu walidacji.

## 11. Stan wykonania (2026-10-06, wieczór)

- Pliki ręczne w `ref/` (w repo; `data/` jest w .gitignore): `crypto_events.csv` (P8, kolumna `verified`: 7 sprawdzonych,
  3 częściowo, 10 nie — lista w raporcie pokrycia), `taxonomy.csv` (20 kodów), `e2_gold_to_label.csv` (150 wierszy;
  ŹRÓDŁO) i `e2_gold_to_label.xlsx` (do oznaczania: lista rozwijana kodów, „niejasne” tak/puste; wczytanie
  `build_causes.py e2-check` porównuje id i tekst z CSV i odrzuca nieznane kody).
- `uv run --frozen src/build_causes.py fetch` — P1, P2, P3a/b, P4 (oryginał EIA z Wayback 2005-11-12), P5 (revid przypięty),
  P7 -> `data/raw/causes/<dzień>/` + manifest; tabele `cause_events`, `bbds_codings`. Liczby: EIA 573 wpisy (494 z dniem),
  Wikipedia 293, DefiLlama 1 290, SF Fed 354 dni, JK 303 dni × 2 szoki, P8 20, BBDS 3 501 kodowań.
- `uv run --frozen src/build_causes.py calendar` — krok 1–2 -> `move_causes` (269 kandydatów), raport
  `reports/move-causes-coverage-2026-10-06.md`; przebieg w `runs` (stage `4N-cal`). Ponowny przebieg: +0 wierszy.
- Warstwa „study” (krok 2b) jeszcze bez etykiet: wpisy chronologii nie mają kodu przyczyny — dostaną go z Twojego złota E2
  albo ze zwalidowanego Qwena; epizody W7 do przepisania.
- Model `qwen3:30b-a3b-instruct-2507-q4_K_M` w trakcie pobierania. Qwen nie był uruchamiany na niczym.
